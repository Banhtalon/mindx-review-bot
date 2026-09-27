import argparse
import asyncio
import importlib
import inspect
import json
import os
import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Final, Protocol, cast

from .browser_driver import ReadonlyBrowserSession, SessionFactory
from .browser_state import BrowserStateCipher, BrowserStateError, EncryptedStateEnvelope
from .live_runner import LiveRunConfig, load_live_config, safe_error_code
from .supabase_client import MAX_RECORDS_READ, ClaimedRun, SupabaseRunnerClient


class RunnerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SafeRunSummary:
    job_id: str
    run_id: str
    status: str
    records_read: int
    error_code: str | None = None


class RunnerClient(Protocol):
    def claim_job_run(self, job_id: str, runner_id: str) -> ClaimedRun:
        ...

    def heartbeat_job(self, job_id: str, runner_id: str) -> None:
        ...

    def finish_job_run(
        self,
        run_id: str,
        runner_id: str,
        status: str,
        *,
        records_read: int,
        error_code: str | None,
        duration_ms: int = 0,
    ) -> None:
        ...


Adapter = Callable[
    [LiveRunConfig, ClaimedRun, ReadonlyBrowserSession], Awaitable[int]
]
SITE_ADAPTER_ENV: Final[str] = "MINDX_SITE_ADAPTER"
ClientFactory = Callable[[LiveRunConfig], RunnerClient]
HEARTBEAT_INTERVAL_SECONDS: Final[float] = 30.0
RUN_TIMEOUT_SECONDS: Final[float] = 12 * 60
CANCELLATION_GRACE_SECONDS: Final[float] = 1.0
FINALIZATION_TIMEOUT_SECONDS: Final[float] = 1.0
CLEANUP_TIMEOUT_SECONDS: Final[float] = 1.0


def _default_client_factory(config: LiveRunConfig) -> RunnerClient:
    return SupabaseRunnerClient(config.supabase_url, config.supabase_secret_key)


def load_configured_adapter(environment: Mapping[str, str]) -> Adapter:
    """Load the explicitly configured async, read-only site adapter.

    The runner deliberately has no implicit live adapter. Deployments must
    name a callable as ``module:attribute`` in ``MINDX_SITE_ADAPTER``. Any
    missing, malformed or unusable configuration maps to the same safe error
    so import details never reach logs or the job result.
    """

    spec = environment.get(SITE_ADAPTER_ENV, "").strip()
    if not spec or spec.count(":") != 1:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    module_name, attribute_name = (part.strip() for part in spec.split(":", 1))
    identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    if (
        not module_name
        or not attribute_name
        or not module_name.startswith("mindx_runner.")
        or any(not identifier.fullmatch(part) for part in module_name.split("."))
        or not identifier.fullmatch(attribute_name)
    ):
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")

    try:
        module = importlib.import_module(module_name)
        candidate = getattr(module, attribute_name)
    except Exception as error:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED") from error

    is_async_callable = inspect.iscoroutinefunction(candidate) or (
        callable(candidate) and inspect.iscoroutinefunction(candidate.__call__)
    )
    if not callable(candidate) or not is_async_callable:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    return cast(Adapter, candidate)


async def _await_with_deadline[ResultT](
    awaitable: Awaitable[ResultT],
    deadline: float,
) -> ResultT:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise RunnerError("RUNNER_TIMEOUT")
    try:
        return await asyncio.wait_for(awaitable, timeout=remaining)
    except TimeoutError as error:
        raise RunnerError("RUNNER_TIMEOUT") from error


async def _finish_run(
    client: RunnerClient,
    run_id: str,
    runner_id: str,
    status: str,
    *,
    records_read: int,
    error_code: str | None,
    duration_ms: int,
    deadline: float,
) -> None:
    await _await_with_deadline(
        asyncio.to_thread(
            client.finish_job_run,
            run_id,
            runner_id,
            status,
            records_read=records_read,
            error_code=error_code,
            duration_ms=duration_ms,
        ),
        deadline,
    )


async def _finish_run_best_effort(
    client: RunnerClient,
    run_id: str,
    runner_id: str,
    *,
    records_read: int,
    error_code: str,
    duration_ms: int,
    deadline: float,
) -> None:
    if deadline <= asyncio.get_running_loop().time():
        return
    try:
        await _finish_run(
            client,
            run_id,
            runner_id,
            "failed",
            records_read=records_read,
            error_code=error_code,
            duration_ms=duration_ms,
            deadline=deadline,
        )
    except Exception:
        return


async def _close_browser_with_bound(
    browser: ReadonlyBrowserSession,
    *,
    wall_deadline: float,
    cleanup_budget: float,
) -> None:
    loop = asyncio.get_running_loop()
    remaining = wall_deadline - loop.time()
    if remaining <= 0:
        return
    timeout = min(cleanup_budget, remaining)
    if timeout <= 0:
        return
    close_task = asyncio.ensure_future(browser.close())
    try:
        await asyncio.wait_for(asyncio.shield(close_task), timeout=timeout)
    except TimeoutError:
        close_task.cancel()
        remaining_after = max(0.0, wall_deadline - loop.time())
        if remaining_after > 0:
            with suppress(asyncio.CancelledError, TimeoutError, Exception):
                await asyncio.wait_for(
                    asyncio.shield(close_task),
                    timeout=min(0.02, remaining_after),
                )
    except Exception:
        pass
    finally:
        await asyncio.sleep(0)


async def _run_adapter_with_heartbeat(
    client: RunnerClient,
    config: LiveRunConfig,
    claimed: ClaimedRun,
    browser: ReadonlyBrowserSession,
    adapter: Adapter,
    *,
    work_deadline: float | None = None,
    cancellation_deadline: float | None = None,
    deadline: float | None = None,
) -> int:
    adapter_task: asyncio.Future[int] = asyncio.ensure_future(adapter(config, claimed, browser))

    def _consume_task(task: asyncio.Future[Any]) -> None:
        if not task.cancelled():
            with suppress(Exception):
                task.exception()

    adapter_task.add_done_callback(_consume_task)
    loop = asyncio.get_running_loop()
    work_limit = (
        work_deadline
        if work_deadline is not None
        else (deadline if deadline is not None else loop.time() + RUN_TIMEOUT_SECONDS)
    )
    cancel_limit = (
        cancellation_deadline
        if cancellation_deadline is not None
        else work_limit + CANCELLATION_GRACE_SECONDS
    )

    async def cancel_adapter() -> None:
        if not adapter_task.done():
            adapter_task.cancel()
            remaining = cancel_limit - loop.time()
            if remaining > 0:
                with suppress(asyncio.CancelledError, TimeoutError, Exception):
                    await asyncio.wait_for(asyncio.shield(adapter_task), timeout=remaining)
            else:
                await asyncio.sleep(0)

    while True:
        remaining = work_limit - loop.time()
        if remaining <= 0:
            await cancel_adapter()
            raise RunnerError("RUNNER_TIMEOUT")
        try:
            return await asyncio.wait_for(
                asyncio.shield(adapter_task),
                timeout=min(HEARTBEAT_INTERVAL_SECONDS, remaining),
            )
        except TimeoutError as error:
            if loop.time() >= work_limit:
                await cancel_adapter()
                raise RunnerError("RUNNER_TIMEOUT") from error
            try:
                await _await_with_deadline(
                    asyncio.to_thread(
                        client.heartbeat_job,
                        config.job_id,
                        config.runner_id,
                    ),
                    work_limit,
                )
            except BaseException:
                await cancel_adapter()
                raise


async def _start_browser_with_bound(
    browser: ReadonlyBrowserSession,
    *,
    work_deadline: float,
    cancellation_deadline: float,
    wall_deadline: float,
) -> None:
    startup_task: asyncio.Future[None] = asyncio.ensure_future(browser.start())

    def _consume_task(task: asyncio.Future[Any]) -> None:
        if not task.cancelled():
            with suppress(Exception):
                task.exception()

    startup_task.add_done_callback(_consume_task)
    loop = asyncio.get_running_loop()

    async def cancel_startup() -> None:
        if not startup_task.done():
            startup_task.cancel()
            remaining_grace = cancellation_deadline - loop.time()
            if remaining_grace > 0:
                with suppress(asyncio.CancelledError, TimeoutError, Exception):
                    await asyncio.wait_for(
                        asyncio.shield(startup_task),
                        timeout=remaining_grace,
                    )
            else:
                await asyncio.sleep(0)

        if not startup_task.done():
            startup_task.cancel()
            remaining_wall = max(0.0, wall_deadline - loop.time())
            if remaining_wall > 0:
                with suppress(asyncio.CancelledError, TimeoutError, Exception):
                    await asyncio.wait_for(
                        asyncio.shield(startup_task),
                        timeout=min(0.02, remaining_wall),
                    )
            else:
                await asyncio.sleep(0)

    remaining_work = work_deadline - loop.time()
    if remaining_work <= 0:
        await cancel_startup()
        raise RunnerError("RUNNER_TIMEOUT")

    try:
        await asyncio.wait_for(asyncio.shield(startup_task), timeout=remaining_work)
    except TimeoutError as error:
        await cancel_startup()
        raise RunnerError("RUNNER_TIMEOUT") from error
    except BaseException:
        await cancel_startup()
        raise


def _claimed_login_paths(claimed: ClaimedRun) -> tuple[str, ...]:
    raw = claimed.payload.get("login_paths", ())
    if raw is None:
        return ()
    if isinstance(raw, str | bytes) or not isinstance(raw, Sequence):
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    paths = tuple(raw)
    if any(
        not isinstance(path, str)
        or not path.startswith("/")
        or "?" in path
        or "#" in path
        for path in paths
    ):
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    return tuple(dict.fromkeys(paths))


def _decode_browser_storage_state(
    encrypted: bytes | None,
    config: LiveRunConfig,
    site: str,
) -> dict[str, object]:
    if encrypted is None:
        raise RunnerError("STORAGE_STATE_DECRYPT_FAILED")
    try:
        envelope = EncryptedStateEnvelope.from_bytes(encrypted)
        plaintext = BrowserStateCipher(
            config.browser_state_key,
            envelope.key_version,
        ).decrypt(envelope, site=site)
        state = json.loads(plaintext.decode("utf-8"))
    except (
        BrowserStateError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise RunnerError("STORAGE_STATE_DECRYPT_FAILED") from error
    if not isinstance(state, dict):
        raise RunnerError("STORAGE_STATE_DECRYPT_FAILED")
    return state


async def _load_browser_storage_state(
    client: RunnerClient,
    config: LiveRunConfig,
    claimed: ClaimedRun,
) -> dict[str, object] | None:
    loader = getattr(client, "load_active_browser_state", None)
    if not callable(loader):
        # Unit fakes and local synthetic runs have no hosted state store. The
        # real Supabase client implements the loader and therefore fails closed.
        return None
    site = "teaching" if config.job_type == "sync_teaching" else "lms"
    encrypted = await asyncio.to_thread(loader, claimed.workspace_id, site)
    return _decode_browser_storage_state(encrypted, config, site)


async def run_job(
    job_id: str,
    environment: Mapping[str, str],
    *,
    client_factory: ClientFactory = _default_client_factory,
    session_factory: SessionFactory | None = None,
    adapter: Adapter | None,
) -> SafeRunSummary:
    values = dict(environment)
    values["JOB_ID"] = job_id
    config = load_live_config(values)
    if adapter is None:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")

    loop = asyncio.get_running_loop()
    wall_deadline = loop.time() + RUN_TIMEOUT_SECONDS
    cleanup_budget = min(CLEANUP_TIMEOUT_SECONDS, max(0.0, RUN_TIMEOUT_SECONDS * 0.15))
    finalization_budget = min(FINALIZATION_TIMEOUT_SECONDS, max(0.0, RUN_TIMEOUT_SECONDS * 0.30))
    cancellation_grace_budget = min(
        CANCELLATION_GRACE_SECONDS,
        max(0.0, RUN_TIMEOUT_SECONDS * 0.15),
    )

    finalization_deadline = wall_deadline - cleanup_budget
    cancellation_deadline = finalization_deadline - finalization_budget
    work_deadline = cancellation_deadline - cancellation_grace_budget

    client = client_factory(config)
    claimed = await _await_with_deadline(
        asyncio.to_thread(client.claim_job_run, config.job_id, config.runner_id),
        work_deadline,
    )
    if not claimed.claimed:
        raise RunnerError("JOB_ALREADY_CLAIMED")

    terminal_call_started = False
    if claimed.job_type != config.job_type:
        terminal_call_started = True
        await _finish_run(
            client,
            claimed.run_id,
            config.runner_id,
            "failed",
            records_read=0,
            error_code="JOB_TYPE_MISMATCH",
            duration_ms=0,
            deadline=finalization_deadline,
        )
        raise RunnerError("JOB_TYPE_MISMATCH")

    browser: ReadonlyBrowserSession | None = None
    browser_started = False
    started_at = 0.0
    try:
        storage_state = await _load_browser_storage_state(client, config, claimed)
        login_paths = _claimed_login_paths(claimed)
        browser = (
            ReadonlyBrowserSession(storage_state=storage_state, login_paths=login_paths)
            if session_factory is None
            else ReadonlyBrowserSession(
                storage_state=storage_state,
                session_factory=session_factory,
                login_paths=login_paths,
            )
        )
        await _start_browser_with_bound(
            browser,
            work_deadline=work_deadline,
            cancellation_deadline=cancellation_deadline,
            wall_deadline=wall_deadline,
        )
        browser_started = True
        started_at = time.monotonic()
        records_read = await _run_adapter_with_heartbeat(
            client,
            config,
            claimed,
            browser,
            adapter,
            work_deadline=work_deadline,
            cancellation_deadline=cancellation_deadline,
        )
        duration_ms = max(0, int((time.monotonic() - started_at) * 1000))
        if (
            type(records_read) is not int
            or records_read < 0
            or records_read > MAX_RECORDS_READ
        ):
            raise RunnerError("RUNNER_RESULT_INVALID")
        terminal_call_started = True
        await _finish_run(
            client,
            claimed.run_id,
            config.runner_id,
            "succeeded",
            records_read=records_read,
            error_code=None,
            duration_ms=duration_ms,
            deadline=finalization_deadline,
        )
        return SafeRunSummary(config.job_id, claimed.run_id, "succeeded", records_read)
    except Exception as error:
        error_code = safe_error_code(error)
        duration_ms = max(0, int((time.monotonic() - started_at) * 1000)) if started_at else 0
        if (browser is None or browser_started) and not terminal_call_started:
            terminal_call_started = True
            await _finish_run_best_effort(
                client,
                claimed.run_id,
                config.runner_id,
                records_read=0,
                error_code=error_code,
                duration_ms=duration_ms,
                deadline=finalization_deadline,
            )
        raise
    finally:
        if browser is not None:
            await _close_browser_with_bound(
                browser,
                wall_deadline=wall_deadline,
                cleanup_budget=cleanup_budget,
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mindx-runner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("job_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    environment = dict(os.environ)
    try:
        if args.command == "preflight":
            config = load_live_config(environment)
            # A successful preflight must prove that the read-only site adapter
            # can actually be imported.  Otherwise the workflow would report
            # a green preflight and fail later, after a job had been claimed.
            load_configured_adapter(environment)
            print(
                json.dumps(
                    {
                        "status": "preflight_ok",
                        "job_id": config.job_id,
                        "job_type": config.job_type,
                    }
                )
            )
            return 0
        # Validate the run environment and resolve the adapter before any job
        # claim or browser startup. Missing or invalid adapter configuration is
        # therefore still fail-closed.
        run_environment = {**environment, "JOB_ID": args.job_id}
        load_live_config(run_environment)
        adapter = load_configured_adapter(environment)
        asyncio.run(run_job(args.job_id, environment, adapter=adapter))
    except Exception as error:
        print(json.dumps({"status": "failed", "error_code": safe_error_code(error)}))
        return 1
    return 0
