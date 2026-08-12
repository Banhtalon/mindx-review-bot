from dataclasses import dataclass

import pytest

from mindx_runner.cli import RunnerError, run_job
from mindx_runner.supabase_client import ClaimedRun

JOB_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
WORKSPACE_ID = "00000000-0000-4000-8000-000000000003"
ENVIRONMENT = {
    "AUTOMATION_ENABLED": "true",
    "MVP_LMS_WRITE_ENABLED": "false",
    "JOB_ID": JOB_ID,
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
    finished: list[tuple[str, str, int, str | None]]

    def claim_job_run(self, job_id: str) -> ClaimedRun:
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
        status: str,
        *,
        records_read: int,
        error_code: str | None,
    ) -> None:
        self.finished.append((run_id, status, records_read, error_code))


@dataclass
class FakeSession:
    closed: bool = False

    async def start(self) -> None:
        pass

    async def open(self, url: str) -> object:
        return object()

    async def stop(self) -> None:
        self.closed = True


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
    assert client.finished == [(RUN_ID, "failed", 0, "LMS_SELECTOR_CHANGED")]
    assert session.closed is True
