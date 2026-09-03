import argparse
import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Final, Protocol

from .browser_driver import ReadonlyBrowserSession, SessionFactory
from .live_runner import LiveRunConfig, load_live_config, safe_error_code
from .supabase_client import ClaimedRun, SupabaseRunnerClient


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
ClientFactory = Callable[[LiveRunConfig], RunnerClient]
HEARTBEAT_INTERVAL_SECONDS: Final[float] = 30.0
RUN_TIMEOUT_SECONDS: Final[float] = 12 * 60
FINALIZATION_TIMEOUT_SECONDS: Final[float] = 1.0
CLEANUP_TIMEOUT_SECONDS: Final[float] = 1.0


def _default_client_factory(config: LiveRunConfig) -> RunnerClient:
    return SupabaseRunnerClient(config.supabase_url, config.supabase_secret_key)


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
    timeout = cleanup_budget if remaining <= 0 else min(cleanup_budget, remaining)
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
        return


async def _run_adapter_with_heartbeat(
    client: RunnerClient,
    config: LiveRunConfig,
    claimed: ClaimedRun,
    browser: ReadonlyBrowserSession,
    adapter: Adapter,
    *,
    deadline: float | None = None,
) -> int:
    adapter_task: asyncio.Future[int] = asyncio.ensure_future(adapter(config, claimed, browser))
    loop = asyncio.get_running_loop()
    run_deadline = deadline if deadline is not None else loop.time() + RUN_TIMEOUT_SECONDS

    async def cancel_adapter() -> None:
        if not adapter_task.done():
            adapter_task.cancel()
            remaining = max(0.0, run_deadline - loop.time())
            if remaining > 0:
                with suppress(asyncio.CancelledError, TimeoutError, Exception):
                    await asyncio.wait_for(asyncio.shield(adapter_task), timeout=remaining)

    while True:
        remaining = run_deadline - loop.time()
        if remaining <= 0:
            await cancel_adapter()
            raise RunnerError("RUNNER_TIMEOUT")
        try:
            return await asyncio.wait_for(
                asyncio.shield(adapter_task),
                timeout=min(HEARTBEAT_INTERVAL_SECONDS, remaining),
            )
        except TimeoutError as error:
            if loop.time() >= run_deadline:
                await cancel_adapter()
                raise RunnerError("RUNNER_TIMEOUT") from error
            try:
                await _await_with_deadline(
                    asyncio.to_thread(
                        client.heartbeat_job,
                        config.job_id,
                        config.runner_id,
                    ),
                    run_deadline,
                )
            except BaseException:
                await cancel_adapter()
                raise


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
    cleanup_budget = min(CLEANUP_TIMEOUT_SECONDS, max(0.0, RUN_TIMEOUT_SECONDS / 5))
    finalization_budget = min(FINALIZATION_TIMEOUT_SECONDS, max(0.0, RUN_TIMEOUT_SECONDS / 5))
    finalization_deadline = wall_deadline - cleanup_budget
    work_deadline = finalization_deadline - finalization_budget

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

    browser = (
        ReadonlyBrowserSession()
        if session_factory is None
        else ReadonlyBrowserSession(session_factory=session_factory)
    )
    browser_started = False
    started_at = 0.0
    try:
        await _await_with_deadline(browser.start(), work_deadline)
        browser_started = True
        started_at = time.monotonic()
        records_read = await _run_adapter_with_heartbeat(
            client,
            config,
            claimed,
            browser,
            adapter,
            deadline=work_deadline,
        )
        duration_ms = max(0, int((time.monotonic() - started_at) * 1000))
        if isinstance(records_read, bool) or records_read < 0:
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
        if browser_started and not terminal_call_started:
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
        asyncio.run(run_job(args.job_id, environment, adapter=None))
    except Exception as error:
        print(json.dumps({"status": "failed", "error_code": safe_error_code(error)}))
        return 1
    return 0
