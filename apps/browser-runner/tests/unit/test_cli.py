import asyncio
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
