import argparse
import asyncio
import json
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

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
    def claim_job_run(self, job_id: str) -> ClaimedRun:
        ...

    def finish_job_run(
        self,
        run_id: str,
        status: str,
        *,
        records_read: int,
        error_code: str | None,
    ) -> None:
        ...


Adapter = Callable[
    [LiveRunConfig, ClaimedRun, ReadonlyBrowserSession], Awaitable[int]
]
ClientFactory = Callable[[LiveRunConfig], RunnerClient]


def _default_client_factory(config: LiveRunConfig) -> RunnerClient:
    return SupabaseRunnerClient(config.supabase_url, config.supabase_secret_key)


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

    client = client_factory(config)
    claimed = client.claim_job_run(config.job_id)
    if not claimed.claimed:
        raise RunnerError("JOB_ALREADY_CLAIMED")

    browser = (
        ReadonlyBrowserSession()
        if session_factory is None
        else ReadonlyBrowserSession(session_factory=session_factory)
    )
    try:
        await browser.start()
        records_read = await adapter(config, claimed, browser)
        if isinstance(records_read, bool) or records_read < 0:
            raise RunnerError("RUNNER_RESULT_INVALID")
        client.finish_job_run(
            claimed.run_id,
            "succeeded",
            records_read=records_read,
            error_code=None,
        )
        return SafeRunSummary(config.job_id, claimed.run_id, "succeeded", records_read)
    except Exception as error:
        error_code = safe_error_code(error)
        client.finish_job_run(
            claimed.run_id,
            "failed",
            records_read=0,
            error_code=error_code,
        )
        raise
    finally:
        await browser.close()

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
