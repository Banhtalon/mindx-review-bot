"""Full Browser Use/guard integration against in-memory synthetic HTTP fixtures.

No external transport: Chromium has a dead loopback proxy and disabled DNS;
Python sockets are loopback-only. Only the last approved Fetch continuation is
fulfilled locally, so multiple interceptors still see the same real request.
No request IDs, URLs, bodies, credentials, HTML or browser state are reported.
"""

import argparse
import asyncio
import base64
import contextlib
import io
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps/browser-runner/src"))
FORM = (
    '<html><body><form method="POST" action="/login.php">'
    '<input name="username"><input name="password" type="password">'
    '<input name="redirect" type="hidden" value="/">'
    '<button type="submit">Synthetic</button></form></body></html>'
)
SUCCESS = '<html><body><div id="synthetic-success">Synthetic response</div></body></html>'


class ChromiumStartupError(RuntimeError):
    def __init__(self, exit_code: int | None = None) -> None:
        self.code = "CHROMIUM_START_TIMEOUT" if exit_code is None else "CHROMIUM_EXITED"
        self.exit_code = exit_code
        super().__init__(self.code)


async def wait_for_chromium(process: Any, profile: Path) -> str:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise ChromiumStartupError(exit_code)
        try:
            with (profile / "DevToolsActivePort").open("rb") as ready:
                data = ready.read(257)
            if len(data) > 256:
                raise ValueError
            port_text, browser_path = data.decode("ascii").splitlines()
            port = int(port_text)
            browser_id = UUID(browser_path.removeprefix("/devtools/browser/"))
            if not 1 <= port <= 65535 or browser_path != f"/devtools/browser/{browser_id}":
                raise ValueError
            return f"ws://127.0.0.1:{port}{browser_path}"
        except (OSError, ValueError):
            # Chrome can still be writing its readiness file. Never report its contents.
            await asyncio.sleep(0.1)
    raise ChromiumStartupError()


async def probe(chromium: str) -> dict[str, Any]:
    import websockets
    from browser_use.browser import BrowserSession

    from mindx_runner.browser_driver import ReadonlyBrowserSession
    from mindx_runner.teaching_auth import LOGIN_URL

    result: dict[str, Any] = {
        "scope": "synthetic full BrowserSession on isolated Chromium",
        "teaching_server_attempts": 0,
        "post_approved": 0,
        "post_blocked": 0,
        "mutation_blocked": 0,
        "fixture_login_responses": 0,
        "login_post_events": 0,
    }
    requests: dict[tuple[str | None, str], dict[str, Any]] = {}
    continued: dict[str, set[str | None]] = {}
    post_sessions: set[str | None] = set()
    network_ids: set[str] = set()
    sdk: Any = None
    browser: Any = None
    original_ws = websockets.connect
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def connect(sock: Any, address: Any) -> Any:
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1"}:
            raise RuntimeError("EXTERNAL_CONNECTION_BLOCKED")
        return original_connect(sock, address)

    def connect_ex(sock: Any, address: Any) -> Any:
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1"}:
            raise RuntimeError("EXTERNAL_CONNECTION_BLOCKED")
        return original_connect_ex(sock, address)

    def local_ws(*args: Any, **kwargs: Any) -> Any:
        kwargs["proxy"] = None
        return original_ws(*args, **kwargs)

    class ObservedBrowser(ReadonlyBrowserSession):
        async def _handle_request_paused(self, event: Any, session_id: str | None = None) -> None:
            requests[(session_id, event["requestId"])] = event
            request = event.get("request") or {}
            if request.get("url") == LOGIN_URL and request.get("method") == "POST":
                result["login_post_events"] += 1
                post_sessions.add(session_id)
                if event.get("networkId"):
                    network_ids.add(event["networkId"])
            await super()._handle_request_paused(event, session_id)

    with (
        tempfile.TemporaryDirectory(prefix="mindx-synthetic-chromium-",
                                    ignore_cleanup_errors=True) as profile,
        patch.object(socket.socket, "connect", connect),
        patch.object(socket.socket, "connect_ex", connect_ex),
        patch.object(websockets, "connect", local_ws),
    ):
        flags = [
            chromium, "--headless", "--remote-debugging-port=0",
            f"--user-data-dir={profile}", "--disable-background-networking",
            "--disable-component-update", "--disable-sync", "--no-first-run",
            "--disable-extensions", "--disable-quic", "--no-pings",
            "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>",
            "--host-resolver-rules=MAP * ~NOTFOUND", "about:blank",
        ]
        if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
            flags.append("--no-sandbox")
        process = subprocess.Popen(
            flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            started = time.monotonic()
            endpoint = await wait_for_chromium(process, Path(profile))
            result["chromium_startup_seconds"] = round(time.monotonic() - started, 3)

            def factory(**options: Any) -> Any:
                nonlocal sdk
                sdk = BrowserSession(cdp_url=endpoint, is_local=False, use_cloud=False, **options)
                return sdk

            browser = ObservedBrowser(session_factory=factory)
            await browser.start()
            fetch = sdk.cdp_client.send.Fetch
            real_continue, real_fail = fetch.continueRequest, fetch.failRequest

            async def continue_fixture(params: Any, session_id: str | None = None) -> Any:
                event = requests[(session_id, params["requestId"])]
                request = event["requestId"]
                data = event["request"]
                manager = sdk.session_manager
                target_session = manager.get_session(session_id)
                target_id = target_session.target_id
                guarded = {
                    s.session_id for s in manager.get_all_sessions_for_target(target_id)
                    if s.session_id in browser._guarded_session_ids
                }
                key = event.get("networkId", request)
                seen = continued.setdefault(key, set())
                seen.add(session_id)
                if len(seen) < len(guarded):
                    return await real_continue(params, session_id=session_id)
                is_login = data["url"] == LOGIN_URL and data["method"] == "POST"
                if is_login:
                    result["post_approved"] += 1
                    result["fixture_login_responses"] += 1
                return await fetch.fulfillRequest(
                    {"requestId": request, "responseCode": 200,
                     "responseHeaders": [{"name": "Content-Type", "value": "text/html"}],
                     "body": base64.b64encode((SUCCESS if is_login else FORM).encode()).decode()},
                    session_id=session_id,
                )

            async def fail_fixture(params: Any, session_id: str | None = None) -> Any:
                data = requests[(session_id, params["requestId"])]["request"]
                if data["method"] == "POST":
                    if data["url"] == LOGIN_URL:
                        result["post_blocked"] += 1
                    else:
                        result["mutation_blocked"] += 1
                return await real_fail(params, session_id=session_id)

            fetch.continueRequest, fetch.failRequest = continue_fixture, fail_fixture
            page = await browser.open(LOGIN_URL)
            for _ in range(100):
                if await page.evaluate(
                    "() => document.querySelector('input[type=password]') ? 'READY' : 'WAITING'"
                ) == "READY":
                    break
                await asyncio.sleep(0.05)
            result["page_session_count"] = len(
                sdk.session_manager.get_all_sessions_for_target(page._target_id)
            )
            try:
                await browser.login_teaching(page, "synthetic-user", "synthetic-value")
                result["login_driver_returned"] = True
            except Exception:
                result["login_driver_returned"] = False
            result["initial_failure"] = browser.teaching_login_failure
            result["initial_post_session_count"] = len(post_sessions)
            result["initial_logical_post_count"] = len(network_ids)
            result["response_observed"] = await page.evaluate(
                "() => document.getElementById('synthetic-success') ? 'YES' : 'NO'"
            ) == "YES"
            if result["response_observed"]:
                # Actual second POST, not a second call to the driver API.
                result["second_post_result"] = await page.evaluate(
                    "() => (async () => { try { await fetch('/login.php', {method:'POST', "
                    "headers:{'Content-Type':'application/x-www-form-urlencoded'}, "
                    "body:'username=synthetic-user&password=synthetic-value&redirect=%2F'}); "
                    "return 'UNEXPECTED'; } catch { return 'BLOCKED'; } })()"
                )
                new_page = await browser.open(LOGIN_URL)
                result["new_page_session_count"] = len(
                    sdk.session_manager.get_all_sessions_for_target(new_page._target_id)
                )
                result["new_target_mutation_result"] = await new_page.evaluate(
                    "() => (async () => { try { "
                    "await fetch('/save.php', {method:'POST',body:'synthetic'}); "
                    "return 'UNEXPECTED'; } catch { return 'BLOCKED'; } })()"
                )
            result["guard_failed"] = browser._guard_failed
        finally:
            if sdk is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(sdk.cdp_client.send.Browser.close(), timeout=2)
            if browser is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(browser.close(), timeout=5)
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chromium", default=shutil.which("google-chrome")
                        or shutil.which("chromium"))
    args = parser.parse_args()
    if not args.chromium or not Path(args.chromium).is_file():
        raise SystemExit("SYNTHETIC_CHROMIUM_REQUIRED")
    os.environ["ANONYMIZED_TELEMETRY"] = "false"
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            async def bounded() -> dict[str, Any]:
                async with asyncio.timeout(80):
                    return await probe(args.chromium)
            result = asyncio.run(bounded())
    except Exception as error:
        # Source locations only; never print exception text, locals or CDP data.
        frames = []
        trace = error.__traceback__
        while trace is not None:
            frames.append({"file": Path(trace.tb_frame.f_code.co_filename).name,
                           "line": trace.tb_lineno})
            trace = trace.tb_next
        failure: dict[str, Any] = {
            "status": "SYNTHETIC_HARNESS_FAILED", "teaching_server_attempts": 0,
            "source_locations": frames,
        }
        if isinstance(error, ChromiumStartupError):
            failure["chromium_startup"] = {"code": error.code, "exit_code": error.exit_code}
        print(json.dumps(failure))
        raise SystemExit(1) from None
    result["passed"] = (
        result["page_session_count"] == 1 and result["initial_post_session_count"] == 1
        and result["initial_logical_post_count"] == 1 and result["initial_failure"] is None
        and result["response_observed"] and result["post_approved"] == 1
        and result.get("second_post_result") == "BLOCKED" and result["post_blocked"] == 1
        and result.get("new_page_session_count") == 1
        and result.get("new_target_mutation_result") == "BLOCKED"
        and result["mutation_blocked"] == 1 and not result["guard_failed"]
    )
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
