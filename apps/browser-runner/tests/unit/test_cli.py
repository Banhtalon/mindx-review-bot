import asyncio
import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from mindx_runner.cli import RunnerError, run_job
from mindx_runner.supabase_client import ClaimedRun

JOB_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
WORKSPACE_ID = "00000000-0000-4000-8000-000000000003"
RUNNER_ID = "runner-test-01"
ENVIRONMENT = {
    "AUTOMATION_ENABLED": "true",
    "MVP_LMS_WRITE_ENABLED": "false",
    "JOB_ID": JOB_ID,
    "RUNNER_ID": RUNNER_ID,
    "JOB_TYPE": "sync_teaching",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SECRET_KEY": "server-secret",
    "BROWSER_STATE_ENCRYPTION_KEY": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
    "TEACHING_USERNAME": "teacher@example.invalid",
    "TEACHING_PASSWORD": "teaching-password",
    "LMS_USERNAME": "lms@example.invalid",
    "LMS_PASSWORD": "lms-password",
}


@dataclass
class FakeClient:
    finished: list[tuple[str, str, int, str | None, int]]
    heartbeats: list[tuple[str, str]] = field(default_factory=list)

    def claim_job_run(self, job_id: str, runner_id: str) -> ClaimedRun:
        assert runner_id == RUNNER_ID
        return ClaimedRun(
            claimed=True,
            run_id=RUN_ID,
            job_id=job_id,
            workspace_id=WORKSPACE_ID,
            job_type="sync_teaching",
            payload={},
            attempt=1,
        )

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
        assert runner_id == RUNNER_ID
        self.finished.append((run_id, status, records_read, error_code, duration_ms))

    def heartbeat_job(self, job_id: str, runner_id: str) -> None:
        self.heartbeats.append((job_id, runner_id))


@dataclass
class FakeSession:
    closed: bool = False
    cdp_client: Any = field(default_factory=lambda: FakeCdp())
    session_manager: Any = field(default_factory=lambda: FakeSessionManager())

    def __post_init__(self) -> None:
        self.session_manager.cdp_client = self.cdp_client

    async def start(self) -> None:
        pass

    async def open(self, url: str) -> object:
        return object()

    async def stop(self) -> None:
        self.closed = True

    async def get_or_create_cdp_session(self, target_id: str, *, focus: bool = False) -> Any:
        return SimpleNamespace(cdp_client=self.cdp_client, session_id=target_id)


class SlowStartSession(FakeSession):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.started_event: asyncio.Event = asyncio.Event()

    async def start(self) -> None:
        self.started_event.set()
        await asyncio.Event().wait()


class SlowStopSession(FakeSession):
    cancelled: bool = False

    async def stop(self) -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


@dataclass
class BlockingFinishClient(FakeClient):
    block_status: str | None = None
    finish_started: asyncio.Event = field(default_factory=asyncio.Event)

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
        super().finish_job_run(
            run_id,
            runner_id,
            status,
            records_read=records_read,
            error_code=error_code,
            duration_ms=duration_ms,
        )
        if self.block_status is None or status == self.block_status:
            self.finish_started.set()
            time.sleep(0.5)


class FakeFetch:
    async def enable(self, **_: object) -> None:
        pass


class FakeTarget:
    async def setAutoAttach(self, **_: object) -> None:
        pass


class FakeFetchRegistration:
    def requestPaused(self, _callback: object) -> None:
        pass


class FakeTargetRegistration:
    def attachedToTarget(self, _callback: object) -> None:
        pass


class FakeRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, object] = {
            "Target.attachedToTarget": lambda *_: None,
        }

    def get_registered_methods(self) -> list[str]:
        return list(self._handlers)

    def register(self, method: str, callback: object) -> None:
        self._handlers[method] = callback


class FakeCdp:
    def __init__(self) -> None:
        self._event_registry = FakeRegistry()
        self.register = SimpleNamespace(
            Fetch=FakeFetchRegistration(),
            Target=FakeTargetRegistration(),
        )
        self.send = SimpleNamespace(Fetch=FakeFetch(), Target=FakeTarget())


class FakeSessionManager:
    cdp_client: Any = None

    def get_all_sessions(self) -> dict[str, object]:
        return {}

    def get_all_targets(self) -> dict[str, object]:
        return {}


@pytest.mark.asyncio
async def test_run_job_requires_site_adapter_before_claiming_or_opening_browser() -> None:
    client = FakeClient([])
    session = FakeSession()

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=None,
        )

    assert error.value.code == "SITE_ADAPTER_NOT_CONFIGURED"
    assert client.finished == []
    assert session.closed is False


@pytest.mark.asyncio
async def test_run_job_finishes_failed_and_closes_browser_when_adapter_errors() -> None:
    client = FakeClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        raise RunnerError("LMS_SELECTOR_CHANGED")

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert error.value.code == "LMS_SELECTOR_CHANGED"
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "LMS_SELECTOR_CHANGED")
    assert client.finished[0][4] >= 0
    assert session.closed is True


@pytest.mark.asyncio
async def test_run_job_rejects_job_type_mismatch_after_claim() -> None:
    client = FakeClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        return 0

    environment = {**ENVIRONMENT, "JOB_TYPE": "read_lms_pending"}
    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            environment,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert error.value.code == "JOB_TYPE_MISMATCH"
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "JOB_TYPE_MISMATCH")
    assert session.closed is False


@pytest.mark.asyncio
async def test_run_job_refreshes_lease_during_a_long_read_only_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    client = FakeClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        await asyncio.sleep(0.04)
        return 2

    summary = await run_job(
        JOB_ID,
        ENVIRONMENT,
        client_factory=lambda _: client,
        session_factory=lambda **_: session,
        adapter=adapter,
    )

    assert summary.status == "succeeded"
    assert len(client.heartbeats) >= 1
    assert client.heartbeats[0] == (JOB_ID, RUNNER_ID)
    assert client.finished[0][:4] == (RUN_ID, "succeeded", 2, None)
    assert session.closed is True


@pytest.mark.asyncio
async def test_run_job_enforces_a_hard_application_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(cli_module, "HEARTBEAT_INTERVAL_SECONDS", 0.005)
    client = FakeClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        await asyncio.sleep(1)
        return 2

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert error.value.code == "RUNNER_TIMEOUT"
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "RUNNER_TIMEOUT")
    assert session.closed is True


@pytest.mark.asyncio
async def test_run_job_applies_the_timeout_before_browser_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = FakeClient([])
    session = SlowStartSession()

    async def adapter(*_: object) -> int:
        return 2

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert error.value.code == "RUNNER_TIMEOUT"
    assert client.finished == []
    assert session.closed is True


@pytest.mark.asyncio
async def test_run_job_keeps_browser_cleanup_inside_the_hard_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = FakeClient([])
    session = SlowStopSession()

    async def adapter(*_: object) -> int:
        return 2

    summary = await asyncio.wait_for(
        run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        ),
        timeout=0.25,
    )

    assert summary.status == "succeeded"
    assert session.cancelled is True
    assert session.closed is False


@pytest.mark.asyncio
async def test_slow_successful_finish_job_run_does_not_double_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = BlockingFinishClient([], block_status="succeeded")
    session = FakeSession()

    async def adapter(*_: object) -> int:
        return 2

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert error.value.code == "RUNNER_TIMEOUT"
    assert [call[1] for call in client.finished] == ["succeeded"]
    assert session.closed is True


@pytest.mark.asyncio
async def test_slow_failed_finalization_preserves_cleanup_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = BlockingFinishClient([], block_status="failed")
    session = FakeSession()

    async def adapter(*_: object) -> int:
        raise RuntimeError("ADAPTER_CRASH")

    with pytest.raises(RuntimeError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert str(error.value) == "ADAPTER_CRASH"
    assert session.closed is True


@pytest.mark.asyncio
async def test_heartbeat_running_at_deadline_does_not_double_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(cli_module, "HEARTBEAT_INTERVAL_SECONDS", 0.005)

    @dataclass
    class SlowHeartbeatClient(FakeClient):
        def heartbeat_job(self, job_id: str, runner_id: str) -> None:
            super().heartbeat_job(job_id, runner_id)
            time.sleep(0.05)

    client = SlowHeartbeatClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        await asyncio.Event().wait()
        return 2

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert error.value.code == "RUNNER_TIMEOUT"
    assert len(client.finished) == 1
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "RUNNER_TIMEOUT")
    assert session.closed is True


@pytest.mark.asyncio
async def test_exhausted_finalization_budget_does_not_issue_terminal_call() -> None:
    from mindx_runner.cli import _finish_run_best_effort

    client = FakeClient([])
    loop = asyncio.get_running_loop()
    past_deadline = loop.time() - 1.0

    await _finish_run_best_effort(
        client,
        RUN_ID,
        RUNNER_ID,
        records_read=0,
        error_code="RUNNER_TIMEOUT",
        duration_ms=0,
        deadline=past_deadline,
    )

    assert client.finished == []


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_result", [-1, True, False, -99])
async def test_invalid_adapter_result_finalizes_only_once(
    invalid_result: Any,
) -> None:
    client = FakeClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        return invalid_result  # type: ignore[return-value]

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert error.value.code == "RUNNER_RESULT_INVALID"
    assert len(client.finished) == 1
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "RUNNER_RESULT_INVALID")
    assert session.closed is True


@pytest.mark.asyncio
async def test_slow_browser_cleanup_is_bound() -> None:
    from mindx_runner.browser_driver import ReadonlyBrowserSession
    from mindx_runner.cli import _close_browser_with_bound

    session = SlowStopSession()
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)
    await browser.start()

    loop = asyncio.get_running_loop()
    wall_deadline = loop.time() + 0.05
    cleanup_budget = 0.02

    start_time = loop.time()
    await _close_browser_with_bound(
        browser,
        wall_deadline=wall_deadline,
        cleanup_budget=cleanup_budget,
    )
    elapsed = loop.time() - start_time

    assert elapsed < 0.1
    assert session.cancelled is True
    assert session.closed is False
