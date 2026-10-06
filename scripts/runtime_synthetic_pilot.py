"""Manual synthetic runtime pilot: real worker/Chromium, RAM backend, no site data."""

import argparse
import asyncio
import base64
import contextlib
import hashlib
import importlib.metadata
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import NAMESPACE_DNS, uuid5

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/browser-runner/src"))
CASES = ("success", "timeout", "hard_stop")
WORKFLOW = "runtime-synthetic-pilot.yml"
REPOSITORY = "Banhtalon/mindx-review-bot"
APPROVAL = "MINDX_RUNTIME_PILOT_APPROVAL_SHA"
HISTORY_URL = (
    f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/{WORKFLOW}"
    "/runs?event=workflow_dispatch&per_page=100"
)


class PilotBlocked(Exception):
    pass


def require(condition, code):
    if not condition:
        raise PilotBlocked(code)


def persist(file, value):
    with file.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def context(environment):
    require(
        environment.get("GITHUB_REPOSITORY") == REPOSITORY
        and environment.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and environment.get("GITHUB_REF") == "refs/heads/main"
        and environment.get("GITHUB_RUN_ATTEMPT") == "1"
        and environment.get("GITHUB_RUN_NUMBER") == "1",
        "RUNTIME_CONTEXT_BLOCKED",
    )
    head, run_id = (
        environment.get("GITHUB_SHA", ""),
        environment.get("GITHUB_RUN_ID", ""),
    )
    require(
        re.fullmatch(r"[a-f0-9]{40}", head)
        and environment.get(APPROVAL) == head
        and re.fullmatch(r"[1-9][0-9]*", run_id),
        "RUNTIME_APPROVAL_REQUIRED",
    )
    require(
        not any(
            name in environment
            for name in (
                "SUPABASE_SECRET_KEY",
                "SUPABASE_SERVICE_ROLE_KEY",
                "BROWSER_STATE_ENCRYPTION_KEY",
                "TEACHING_USERNAME",
                "TEACHING_PASSWORD",
            )
        ),
        "RUNTIME_ACCOUNT_ENV_BLOCKED",
    )
    return head, run_id


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def history_once(token):
    request = Request(
        HISTORY_URL,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    with build_opener(NoRedirect()).open(request, timeout=30) as response:
        require(response.status == 200, "RUNTIME_HISTORY_REJECTED")
        raw = response.read(65_537)
        require(len(raw) <= 65_536, "RUNTIME_HISTORY_TOO_LARGE")
        return raw


def preflight(environment, file, transport=history_once):
    file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with file.open("x", encoding="utf-8") as stream:
            stream.write("{}")
    except FileExistsError:
        return {"status": "BLOCKED", "error_code": "RUNTIME_ALREADY_ATTEMPTED"}
    receipt = {"status": "PREFLIGHT_STARTED", "github_reads": 0, "cases": []}
    persist(file, receipt)
    try:
        head, run_id = context(environment)
        require(environment.get("GITHUB_TOKEN"), "RUNTIME_HISTORY_CREDENTIAL_REQUIRED")
        receipt.update(
            head=head, run_id=run_id, github_reads=1, history_outcome="UNKNOWN"
        )
        persist(
            file, receipt
        )  # A failed read consumes its allowance before transmission.
        history = json.loads(transport(environment["GITHUB_TOKEN"]))
        runs = history.get("workflow_runs")
        require(
            type(history.get("total_count")) is int
            and history["total_count"] == 1
            and isinstance(runs, list)
            and len(runs) == 1,
            "RUNTIME_PRIOR_OR_AMBIGUOUS_DISPATCH",
        )
        run = runs[0]
        require(
            isinstance(run, dict)
            and type(run.get("id")) is int
            and run["id"] == int(run_id)
            and run.get("head_sha") == head
            and run.get("head_branch") == "main"
            and run.get("event") == "workflow_dispatch"
            and type(run.get("run_attempt")) is int
            and run["run_attempt"] == 1
            and type(run.get("run_number")) is int
            and run["run_number"] == 1,
            "RUNTIME_PRIOR_OR_AMBIGUOUS_DISPATCH",
        )
        receipt.update(
            status="PREFLIGHT_PASS", history_outcome="FIRST_DISPATCH_CONFIRMED"
        )
    except PilotBlocked as error:
        receipt.update(status="BLOCKED", error_code=str(error))
    except Exception:
        receipt.update(status="BLOCKED", error_code="RUNTIME_HISTORY_UNAVAILABLE")
    persist(file, receipt)
    return receipt


def consume_preflight(environment, file):
    """Consume once before any worker; token is confined to the preceding step."""
    head, run_id = context(environment)
    require("GITHUB_TOKEN" not in environment, "RUNTIME_TOKEN_SCOPE_BLOCKED")
    receipt = json.loads(file.read_text(encoding="utf-8"))
    require(
        receipt
        == {
            "status": "PREFLIGHT_PASS",
            "github_reads": 1,
            "cases": [],
            "head": head,
            "run_id": run_id,
            "history_outcome": "FIRST_DISPATCH_CONFIRMED",
        },
        "RUNTIME_PREFLIGHT_REQUIRED",
    )
    receipt["status"] = "RUNTIME_STARTED"
    persist(file, receipt)
    return receipt


def owned_process(identity):
    try:
        process = psutil.Process(identity["pid"])
        if process.create_time() == identity["created"] and process.is_running():
            return process
    except psutil.NoSuchProcess:
        pass
    return None  # AccessDenied propagates: unknown cannot certify cleanup.


def running(identity):
    process = owned_process(identity)
    try:
        return (
            process
            if process is not None and process.status() != psutil.STATUS_ZOMBIE
            else None
        )
    except psutil.NoSuchProcess:
        return None


def zombie_pids(owned):
    result = []
    for identity in owned.values():
        process = owned_process(identity)
        try:
            if process is not None and process.status() == psutil.STATUS_ZOMBIE:
                result.append(identity["pid"])
        except psutil.NoSuchProcess:
            pass
    return result


def observe_children(identity, owned):
    process = running(identity)
    if process is not None:
        for child in process.children(recursive=True):
            try:
                owned[child.pid] = {
                    "pid": child.pid,
                    "created": child.create_time(),
                    "name": child.name(),
                }
            except psutil.NoSuchProcess:
                pass


def read_events(folder):
    file = folder / "events.jsonl"
    return (
        [json.loads(line) for line in file.read_text().splitlines()]
        if file.exists()
        else []
    )


def worker(case, folder, chromium, smoke):
    start = time.monotonic()

    def event(kind, **details):
        with (folder / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {"event": kind, "seconds": time.monotonic() - start, **details}
                )
                + "\n"
            )

    connect, connect_ex = socket.socket.connect, socket.socket.connect_ex

    def allowed_call(original, sock, address):
        require(
            isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"},
            "RUNTIME_EXTERNAL_CONNECTION_BLOCKED",
        )
        return original(sock, address)

    socket.socket.connect = lambda sock, address: allowed_call(connect, sock, address)
    socket.socket.connect_ex = lambda sock, address: allowed_call(
        connect_ex, sock, address
    )
    logging.disable(logging.CRITICAL)
    import websockets
    from browser_use.browser import BrowserSession

    from mindx_runner import cli
    from mindx_runner.supabase_client import ClaimedRun

    original_ws = websockets.connect

    def local_ws(*args, **kwargs):
        kwargs["proxy"] = None
        return original_ws(*args, **kwargs)

    websockets.connect = local_ws
    require(
        cli.RUN_TIMEOUT_SECONDS == 720 and cli.HEARTBEAT_INTERVAL_SECONDS == 30,
        "RUNTIME_DEFAULTS_CHANGED",
    )
    if smoke and case == "timeout":
        cli.RUN_TIMEOUT_SECONDS = 35  # Only Windows/local smoke, never the cloud mode.
    job, run, workspace = (
        str(uuid5(NAMESPACE_DNS, name))
        for name in (
            "runtime-pilot-" + case,
            "runtime-pilot-run-" + case,
            "runtime-pilot-workspace",
        )
    )
    sdk = None

    class RecordingClient:
        # ponytail: RAM recording seam; API/lease/persistence need a separate accepted pilot.
        def claim_job_run(self, job_id, runner_id):
            require(job_id == job, "RUNTIME_JOB_MISMATCH")
            event("claim")
            return ClaimedRun(
                True, run, job, workspace, "sync_teaching", {"synthetic": True}, 1
            )

        def heartbeat_job(self, job_id, runner_id):
            require(job_id == job, "RUNTIME_JOB_MISMATCH")
            event("heartbeat")

        def finish_job_run(
            self, run_id, runner_id, status, *, records_read, error_code, duration_ms=0
        ):
            require(run_id == run and records_read == 0, "RUNTIME_RESULT_INVALID")
            event(
                "finish",
                status=status,
                error_code=error_code,
                records=records_read,
                duration_ms=duration_ms,
            )

    def factory(**options):
        nonlocal sdk
        sdk = BrowserSession(
            **options,
            is_local=True,
            use_cloud=False,
            executable_path=chromium,
            user_data_dir=str(folder / "profile"),
            chromium_sandbox=os.environ.get("GITHUB_ACTIONS") != "true",
            args=[
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
                "--no-first-run",
                "--disable-quic",
                "--no-pings",
                "--proxy-server=http://127.0.0.1:9",
                "--proxy-bypass-list=<-loopback>",
                "--host-resolver-rules=MAP * ~NOTFOUND",
            ],
        )
        return sdk

    async def adapter(config, claimed, browser):
        require(
            sdk is not None and browser._session is sdk and not browser._guard_failed,
            "RUNTIME_BROWSER_REQUIRED",
        )
        targets = sdk.session_manager.get_all_targets()
        require(targets, "RUNTIME_BROWSER_REQUIRED")
        event("browser_ready", target_count=len(targets))
        try:
            if case == "success":
                await asyncio.sleep(35 if smoke else 650)
                event("adapter_done")
                return 0
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            event("adapter_cancelled")
            raise

    environment = {
        "AUTOMATION_ENABLED": "true",
        "MVP_LMS_WRITE_ENABLED": "false",
        "JOB_ID": job,
        "RUNNER_ID": "synthetic-runtime-" + case,
        "JOB_TYPE": "sync_teaching",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SECRET_KEY": "public-synthetic-unused-value",
        "BROWSER_STATE_ENCRYPTION_KEY": base64.b64encode(bytes(range(32))).decode(),
    }
    event("worker_started", wall_seconds=cli.RUN_TIMEOUT_SECONDS, heartbeat_seconds=30)
    try:
        summary = asyncio.run(
            cli.run_job(
                job,
                environment,
                client_factory=lambda _: RecordingClient(),
                session_factory=factory,
                adapter=adapter,
            )
        )
        event("worker_result", status=summary.status, records=summary.records_read)
    except Exception as error:
        event("worker_result", status="failed", error_code=cli.safe_error_code(error))
    finally:
        event("worker_returned")


def verify_case(case, events, exit_code, killed, residual, smoke, elapsed):
    def select(kind):
        return [e for e in events if e["event"] == kind]

    require(
        len(select("worker_started")) == 1
        and len(select("claim")) == 1
        and len(select("browser_ready")) == 1,
        "RUNTIME_EVENTS_INVALID",
    )
    require(select("browser_ready")[0]["target_count"] > 0, "RUNTIME_BROWSER_REQUIRED")
    require(
        select("worker_started")[0]["heartbeat_seconds"] == 30,
        "RUNTIME_DEFAULTS_CHANGED",
    )
    wall = 35 if smoke and case == "timeout" else 720
    require(
        select("worker_started")[0]["wall_seconds"] == wall, "RUNTIME_DEFAULTS_CHANGED"
    )
    if case == "hard_stop":
        require(
            killed
            and exit_code != 0
            and not select("finish")
            and not select("worker_result")
            and not select("worker_returned"),
            "RUNTIME_HARD_STOP_INVALID",
        )
        return
    require(
        exit_code == 0
        and not killed
        and not residual
        and len(select("finish")) == 1
        and len(select("worker_result")) == 1
        and len(select("worker_returned")) == 1,
        "RUNTIME_TERMINAL_OR_CLEANUP_INVALID",
    )
    finish, result = select("finish")[0], select("worker_result")[0]
    require(finish["records"] == 0, "RUNTIME_RESULT_INVALID")
    if case == "success":
        hold = 35 if smoke else 650
        require(
            finish["status"] == result["status"] == "succeeded"
            and finish["error_code"] is None
            and len(select("adapter_done")) == 1,
            "RUNTIME_SUCCESS_INVALID",
        )
        require(
            select("adapter_done")[0]["seconds"] - select("browser_ready")[0]["seconds"]
            >= hold
            and len(select("heartbeat")) >= (1 if smoke else 20),
            "RUNTIME_HEARTBEAT_MISSING",
        )
        if not smoke:
            require(
                select("heartbeat")[-1]["seconds"]
                - select("browser_ready")[0]["seconds"]
                >= 600,
                "RUNTIME_HEARTBEAT_MISSING",
            )
    else:
        require(
            finish["status"] == result["status"] == "failed"
            and finish["error_code"] == result.get("error_code") == "RUNNER_TIMEOUT"
            and len(select("adapter_cancelled")) == 1,
            "RUNTIME_TIMEOUT_INVALID",
        )
        cancel = select("adapter_cancelled")[0]["seconds"]
        require(cancel <= finish["seconds"], "RUNTIME_TIMEOUT_INVALID")
        delta = cancel - select("claim")[0]["seconds"]
        require(
            wall - 4 <= delta <= wall - 1 and elapsed <= wall + 8,
            "RUNTIME_TIMEOUT_CLOCK_INVALID",
        )
    heartbeat = select("heartbeat")
    require(
        heartbeat
        and heartbeat[0]["seconds"] - select("browser_ready")[0]["seconds"] >= 29.5,
        "RUNTIME_HEARTBEAT_CLOCK_INVALID",
    )


def supervise(case, base, chromium, smoke):
    folder = base / case
    folder.mkdir()
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        in {
            "SYSTEMROOT",
            "WINDIR",
            "PATH",
            "TEMP",
            "TMP",
            "APPDATA",
            "LOCALAPPDATA",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "GITHUB_ACTIONS",
        }
    }
    env.update(
        ANONYMIZED_TELEMETRY="false", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1"
    )
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        case,
        "--receipt",
        str(base / "receipt.json"),
        "--chromium",
        chromium,
    ]
    if smoke:
        command.append("--worker-smoke")
    begun = time.monotonic()
    cap = (
        90
        if smoke and case == "success"
        else (50 if smoke or case == "hard_stop" else 750)
    )
    owned, p, ready_at, killed = {}, None, None, False
    receipt = {"case": case, "status": "FAILED", "safe_error": None}
    try:
        p = subprocess.Popen(
            command,
            env=env,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name == "posix",
        )
        parent = {"pid": p.pid, "created": psutil.Process(p.pid).create_time()}
        if os.name == "posix":
            require(os.getsid(p.pid) == p.pid, "RUNTIME_PROCESS_SESSION_INVALID")
            receipt["worker_session_id"] = p.pid
        while p.poll() is None:
            observe_children(parent, owned)
            if ready_at is None and any(
                e["event"] == "browser_ready" for e in read_events(folder)
            ):
                ready_at = time.monotonic()
            if (
                case == "hard_stop"
                and ready_at is not None
                and time.monotonic() - ready_at >= 3
            ):
                require(running(parent), "RUNTIME_WORKER_IDENTITY_UNKNOWN")
                observe_children(parent, owned)
                p.kill()
                killed = True
                break
            require(time.monotonic() - begun <= cap, "RUNTIME_SUPERVISOR_WALL_EXCEEDED")
            time.sleep(0.1)
        p.wait(timeout=5)
        for identity in list(owned.values()):
            observe_children(identity, owned)
        time.sleep(0.5)
        residual = [i for i in owned.values() if running(i)]
        events = read_events(folder)
        receipt.update(
            worker_exit_code=p.returncode,
            worker_killed=killed,
            events=events,
            owned_processes=list(owned.values()),
            residual_before_supervisor_cleanup=residual,
            elapsed_seconds=time.monotonic() - begun,
        )
        require(
            any(
                i["name"].lower() in {"chrome.exe", "chrome", "chromium"}
                for i in owned.values()
            ),
            "RUNTIME_BROWSER_PROCESS_MISSING",
        )
        verify_case(
            case,
            events,
            p.returncode,
            killed,
            residual,
            smoke,
            receipt["elapsed_seconds"],
        )
        receipt["status"] = "PASS"
    except PilotBlocked as error:
        receipt["safe_error"] = str(error)
    except Exception:
        receipt["safe_error"] = "RUNTIME_OBSERVATION_FAILED"
    finally:
        # ponytail: bounded PID observation, not atomic OS containment or crash-proof supervisor.
        try:
            if p is not None and p.poll() is None:
                p.kill()
                p.wait(timeout=5)
            for identity in list(owned.values()):
                observe_children(identity, owned)
            for identity in reversed(list(owned.values())):
                process = running(identity)
                if process is not None:
                    with contextlib.suppress(psutil.NoSuchProcess):
                        process.kill()
            deadline = time.monotonic() + 5
            while (
                any(running(i) for i in owned.values()) and time.monotonic() < deadline
            ):
                time.sleep(0.1)
            remaining = [i for i in owned.values() if running(i)]
            receipt["residual_after_supervisor_cleanup"] = remaining
            receipt["zombie_pids"] = zombie_pids(owned)
            require(not remaining, "RUNTIME_CLEANUP_FAILED")
            profile = (folder / "profile").resolve()
            require(
                profile.parent == folder.resolve()
                and profile.is_relative_to(base.resolve()),
                "RUNTIME_PROFILE_BOUNDARY_FAILED",
            )
            if profile.exists():
                shutil.rmtree(profile)
            receipt["owned_profile_removed"] = not profile.exists()
        except Exception:
            receipt.update(status="FAILED", safe_error="RUNTIME_CLEANUP_UNCONFIRMED")
        receipt["total_seconds"] = time.monotonic() - begun
        persist(folder / "receipt.json", receipt)
    return receipt


def execute_runtime(receipt, file, chromium, smoke):
    require(Path(chromium).is_file(), "RUNTIME_CHROMIUM_REQUIRED")
    require(
        importlib.metadata.version("browser-use") == "0.13.6", "RUNTIME_SDK_CHANGED"
    )
    receipt.update(
        mode="local_smoke" if smoke else "cloud",
        recording_backend_only=True,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    for case in CASES:
        receipt["case_intent"] = case
        persist(file, receipt)  # Persist attempted case before launching, never retry.
        case_receipt = supervise(case, file.parent, chromium, smoke)
        receipt["cases"].append(case_receipt)
        persist(file, receipt)
        if case_receipt["status"] != "PASS":
            break
    receipt["status"] = (
        "PASS"
        if len(receipt["cases"]) == 3
        and all(c["status"] == "PASS" for c in receipt["cases"])
        else "FAILED"
    )
    persist(file, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--cloud", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--worker", choices=CASES)
    parser.add_argument("--worker-smoke", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--chromium")
    args = parser.parse_args()
    file = args.receipt.resolve()
    try:
        if args.worker:
            # Only the supervisor's already-created case directory can be used.
            require(
                file.parent.joinpath(args.worker).is_dir(),
                "RUNTIME_WORKER_SCOPE_INVALID",
            )
            worker(
                args.worker, file.parent / args.worker, args.chromium, args.worker_smoke
            )
            return
        if args.preflight:
            result = preflight(os.environ, file)
        else:
            if args.cloud:
                require(
                    os.name == "posix" and os.environ.get("GITHUB_ACTIONS") == "true",
                    "RUNTIME_HOST_REQUIRED",
                )
                result = consume_preflight(os.environ, file)
            else:
                require(not os.environ.get("GITHUB_ACTIONS"), "RUNTIME_LOCAL_ONLY")
                file.parent.mkdir(parents=True, exist_ok=True)
                with file.open("x", encoding="utf-8") as stream:
                    json.dump({"status": "SMOKE_STARTED", "cases": []}, stream)
                result = {"status": "SMOKE_STARTED", "cases": []}
            result = execute_runtime(result, file, args.chromium, args.smoke)
        print(
            json.dumps(
                {"status": result["status"], "error_code": result.get("error_code")}
            )
        )
        raise SystemExit(0 if result["status"] in {"PASS", "PREFLIGHT_PASS"} else 1)
    except Exception:
        print('{"status":"BLOCKED","error_code":"RUNTIME_SCOPE_OR_CAPABILITY_BLOCKED"}')
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
