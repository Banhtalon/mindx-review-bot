from dataclasses import replace

import pytest

from mindx_runner.browser_state import BrowserStateError
from mindx_runner.hosted_probe import (
    SYNTHETIC_STATE,
    HostedProbeConfig,
    cleanup_probe,
    persist_state,
    reuse_and_reset_state,
    run_database_probe,
)
from mindx_runner.supabase_client import (
    BrowserStateRecord,
    ClaimedRun,
    EnqueuedProbeJob,
    SupabaseClientError,
)

PROBE_ID = "00000000-0000-4000-8000-000000000011"
WORKSPACE_ID = "00000000-0000-4000-8000-000000000012"
KEY = b"k" * 32
PATH = f"browser-state/{WORKSPACE_ID}/lms/{PROBE_ID}.json"
JOB_ID = "00000000-0000-4000-8000-000000000013"
RUN_IDS = [
    "00000000-0000-4000-8000-000000000021",
    "00000000-0000-4000-8000-000000000022",
    "00000000-0000-4000-8000-000000000023",
]


class FakeClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.active: BrowserStateRecord | None = None
        self.deleted_rows: list[tuple[str, str]] = []
        self.cleanup_failures = 0
        self.object_store = self

    def put(self, path: str, value: bytes) -> None:
        self.objects[path] = value

    def get(self, path: str) -> bytes:
        return self.objects[path]

    def delete(self, path: str) -> None:
        self.objects.pop(path, None)

    def get_active_browser_state(self, workspace_id: str, site: str) -> BrowserStateRecord | None:
        return self.active

    def activate_browser_state_version(
        self,
        workspace_id: str,
        site: str,
        version_id: str,
        object_path: str,
        key_version: int,
        state_hash: str,
    ) -> None:
        self.active = BrowserStateRecord(
            version_id,
            workspace_id,
            site,
            object_path,
            key_version,
            state_hash,
            "active",
        )

    def reset_browser_state(self, workspace_id: str, site: str) -> str | None:
        if self.active is None:
            return None
        path = self.active.object_path
        self.active = None
        return path

    def delete_probe_rows(self, version_id: str, idempotency_key: str) -> None:
        if self.cleanup_failures > 0:
            self.cleanup_failures -= 1
            raise SupabaseClientError("SUPABASE_UNAVAILABLE")
        self.deleted_rows.append((version_id, idempotency_key))


def config() -> HostedProbeConfig:
    return HostedProbeConfig(PROBE_ID, WORKSPACE_ID, "lms", KEY, RUN_IDS[0])


class FakeDeniedClient:
    def claim_job_run(self, job_id: str, runner_id: str) -> ClaimedRun:
        raise SupabaseClientError("SUPABASE_UNAVAILABLE")


class FakeDatabaseClient:
    def __init__(self) -> None:
        self.attempt = 0
        self.active: ClaimedRun | None = None
        self.finished: list[tuple[str, str, str]] = []
        self.expired = False

    def enqueue_probe_job(
        self, workspace_id: str, requested_by: str, probe_id: str
    ) -> EnqueuedProbeJob:
        return EnqueuedProbeJob(
            JOB_ID,
            workspace_id,
            "read_lms_pending",
            "queued",
            f"phase2-probe:{probe_id}",
            True,
        )

    def claim_job_dispatch(self, job_id: str) -> bool:
        return True

    def finish_job_dispatch(self, job_id: str) -> None:
        return None

    def claim_job_run(self, job_id: str, runner_id: str) -> ClaimedRun:
        if self.active is not None and not self.expired:
            return replace(self.active, claimed=False)
        if self.expired:
            self.active = None
            self.expired = False
        if self.attempt >= 3:
            raise SupabaseClientError("SUPABASE_UNAVAILABLE")
        self.attempt += 1
        claimed = ClaimedRun(
            True,
            RUN_IDS[self.attempt - 1],
            JOB_ID,
            WORKSPACE_ID,
            "read_lms_pending",
            {},
            self.attempt,
        )
        self.active = claimed
        return claimed

    def heartbeat_job(self, job_id: str, runner_id: str) -> None:
        if self.active is None or not runner_id.endswith(str(self.attempt)):
            raise SupabaseClientError("SUPABASE_UNAVAILABLE")

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
        if self.active is None or self.active.run_id != run_id or not runner_id.endswith(
            str(self.attempt)
        ):
            raise SupabaseClientError("SUPABASE_UNAVAILABLE")
        self.finished.append((status, error_code or "", str(records_read)))
        self.active = None

    def expire_probe_lease(self, job_id: str) -> None:
        self.expired = True


def test_state_persist_and_separate_reuse_reset_use_only_synthetic_bytes() -> None:
    client = FakeClient()

    persisted = persist_state(config(), client)
    reused = reuse_and_reset_state(config(), client)

    assert persisted.status == "persisted"
    assert persisted.version_id == PROBE_ID
    assert persisted.byte_count > len(SYNTHETIC_STATE)
    assert reused.status == "reset"
    assert reused.state_hash == persisted.state_hash
    assert PATH not in client.objects
    assert client.active is None


def test_state_persist_refuses_to_replace_an_existing_active_version() -> None:
    client = FakeClient()
    client.active = BrowserStateRecord(
        PROBE_ID,
        WORKSPACE_ID,
        "lms",
        PATH,
        1,
        "a" * 64,
        "active",
    )

    with pytest.raises(RuntimeError, match="HOSTED_PROBE_NOT_ISOLATED"):
        persist_state(config(), client)

    assert client.objects == {}


def test_state_reuse_rejects_tampered_encrypted_bytes() -> None:
    client = FakeClient()
    persist_state(config(), client)
    assert client.active is not None
    encrypted = bytearray(client.objects[PATH])
    encrypted[-2] = ord("A") if encrypted[-2] != ord("A") else ord("B")
    client.objects[PATH] = bytes(encrypted)

    with pytest.raises(BrowserStateError):
        reuse_and_reset_state(config(), client)


def test_state_reuse_rejects_wrong_active_version() -> None:
    client = FakeClient()
    persist_state(config(), client)
    assert client.active is not None
    client.active = replace(
        client.active,
        version_id="00000000-0000-4000-8000-000000000099",
    )

    with pytest.raises(RuntimeError, match="HOSTED_PROBE_STATE_MISMATCH"):
        reuse_and_reset_state(config(), client)


def test_cleanup_is_exact_and_idempotent() -> None:
    client = FakeClient()
    persist_state(config(), client)

    first = cleanup_probe(config(), client)
    second = cleanup_probe(config(), client)

    expected_key = f"phase2-probe:{PROBE_ID}"
    assert first.status == "cleaned"
    assert second.status == "cleaned"
    assert client.deleted_rows == [(PROBE_ID, expected_key), (PROBE_ID, expected_key)]
    assert client.objects == {}


def test_database_probe_checks_contention_ownership_expiry_and_attempt_bound() -> None:
    client = FakeDatabaseClient()

    summary = run_database_probe(
        config(),
        client,
        denied_clients=(FakeDeniedClient(), FakeDeniedClient()),
    )

    assert summary.status == "database_pass"
    assert summary.attempts == 3
    assert summary.role_boundary_checks == 2
    assert client.attempt == 3
    assert all(status == "failed" for status, _, _ in client.finished)
    assert all(code == "HOSTED_PROBE_CANCELLED" for _, code, _ in client.finished)
    assert "succeeded" not in {status for status, _, _ in client.finished}


def test_cleanup_retries_one_transient_exact_row_failure() -> None:
    client = FakeClient()
    client.cleanup_failures = 1
    persist_state(config(), client)

    summary = cleanup_probe(config(), client)

    assert summary.status == "cleaned"
    assert client.cleanup_failures == 0
    assert client.deleted_rows == [(PROBE_ID, f"phase2-probe:{PROBE_ID}")]
