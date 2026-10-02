import asyncio
import json
import sys
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from mindx_runner.browser_driver import BrowserStartupError
from mindx_runner.browser_state import BrowserStateCipher
from mindx_runner.cli import RunnerError, load_configured_adapter, main, run_job
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
TARGET_DATA = {
    "workspace_id": WORKSPACE_ID,
    "teaching_url": "https://teachingmindx.top/schedule",
    "class_code": "SYN-ROBOTICS-01",
    "session_number": 3,
    "scheduled_date": "2026-09-27",
    "start_time": "09:00:00",
    "end_time": "10:00:00",
}


def test_bootstrap_browser_state_reads_local_file_and_never_prints_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = (
        b'{"cookies":[{"name":"sid","value":"secret-cookie",'
        b'"domain":".teachingmindx.top","path":"/"}],"origins":[]}'
    )
    state_path = tmp_path / "state.json"
    state_path.write_bytes(state)
    observed: dict[str, object] = {}

    class FakeSupabase:
        def __init__(self, url: str, secret: str) -> None:
            observed["url"] = url
            observed["secret"] = secret

        def persist_browser_state(
            self,
            workspace_id: str,
            site: str,
            storage_state: bytes,
            cipher: BrowserStateCipher,
        ) -> Any:
            observed["workspace_id"] = workspace_id
            observed["site"] = site
            observed["storage_state"] = storage_state
            observed["key_version"] = cipher.key_version
            return type("Version", (), {"site": site})()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "server-secret")
    monkeypatch.setenv("BROWSER_STATE_ENCRYPTION_KEY", ENVIRONMENT["BROWSER_STATE_ENCRYPTION_KEY"])
    monkeypatch.setattr("mindx_runner.cli.SupabaseRunnerClient", FakeSupabase)

    assert main(
        [
            "bootstrap-browser-state",
            "--site",
            "teaching",
            "--workspace-id",
            WORKSPACE_ID,
            "--state-path",
            str(state_path),
            "--key-version",
            "4",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "browser_state_uploaded" in output
    assert "secret-cookie" not in output
    assert observed["workspace_id"] == WORKSPACE_ID
    assert observed["site"] == "teaching"
    assert observed["storage_state"] == state
    assert observed["key_version"] == 4


def test_bootstrap_browser_state_rejects_noncanonical_supabase_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_bytes(b'{"cookies":[],"origins":[]}')
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co/path")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "server-secret")
    monkeypatch.setenv("BROWSER_STATE_ENCRYPTION_KEY", ENVIRONMENT["BROWSER_STATE_ENCRYPTION_KEY"])

    class UnexpectedClient:
        def __init__(self, *_: object) -> None:
            pytest.fail("Supabase client must not receive an unsafe URL")

    monkeypatch.setattr("mindx_runner.cli.SupabaseRunnerClient", UnexpectedClient)

    assert main(
        [
            "bootstrap-browser-state",
            "--site",
            "teaching",
            "--workspace-id",
            WORKSPACE_ID,
            "--state-path",
            str(state_path),
        ]
    ) == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "error_code": "LIVE_CONFIG_INVALID",
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
    stop_calls: int = 0
    cdp_client: Any = field(default_factory=lambda: FakeCdp())
    session_manager: Any = field(default_factory=lambda: FakeSessionManager())

    def __post_init__(self) -> None:
        self.session_manager.cdp_client = self.cdp_client

    async def start(self) -> None:
        pass

    async def open(self, url: str) -> object:
        return object()

    async def stop(self) -> None:
        self.stop_calls += 1
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
        self.stop_calls += 1
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class SlowStartCleanupSession(FakeSession):
    async def start(self) -> None:
        await asyncio.Event().wait()

    async def stop(self) -> None:
        self.stop_calls += 1
        await asyncio.sleep(0.2)
        self.closed = True


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
            time.sleep(0.09)


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

    async def _handle_target_attached(self, _event: dict[str, object]) -> None:
        return None


def test_load_configured_adapter_requires_explicit_configuration() -> None:
    with pytest.raises(RunnerError) as error:
        load_configured_adapter({})

    assert error.value.code == "SITE_ADAPTER_NOT_CONFIGURED"


def test_load_configured_adapter_loads_async_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("mindx_runner.test_site_adapter")

    async def adapter(*_: object) -> int:
        return 0

    module.adapter = adapter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)

    loaded = load_configured_adapter(
        {"MINDX_SITE_ADAPTER": "mindx_runner.test_site_adapter:adapter"}
    )

    assert loaded is adapter


@pytest.mark.parametrize(
    "spec",
    [
        "test_site_adapter",
        "mindx_runner.test_site_adapter:missing",
        "test-site-adapter:adapter",
        "test_site_adapter:adapter:extra",
        "os:system",
    ],
)
def test_load_configured_adapter_rejects_invalid_configuration(spec: str) -> None:
    with pytest.raises(RunnerError) as error:
        load_configured_adapter({"MINDX_SITE_ADAPTER": spec})

    assert error.value.code == "SITE_ADAPTER_NOT_CONFIGURED"


def test_preflight_fails_before_claim_when_site_adapter_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("MINDX_SITE_ADAPTER", raising=False)

    assert main(["preflight"]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output == {
        "status": "failed",
        "error_code": "SITE_ADAPTER_NOT_CONFIGURED",
    }


def test_preflight_only_succeeds_with_importable_async_site_adapter(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = ModuleType("mindx_runner.preflight_site_adapter")

    async def adapter(*_: object) -> int:
        return 0

    module.adapter = adapter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(
        "MINDX_SITE_ADAPTER",
        "mindx_runner.preflight_site_adapter:adapter",
    )

    assert main(["preflight"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "preflight_ok"
    assert output["job_id"] == JOB_ID
    assert output["job_type"] == "sync_teaching"


def test_preflight_rejects_malformed_trusted_target_without_creating_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("MINDX_TEACHING_TARGET_JSON", "{malformed-private-value}")
    monkeypatch.delenv("MINDX_SITE_ADAPTER", raising=False)

    class UnexpectedClient:
        def __init__(self, *_: object) -> None:
            pytest.fail("Invalid target must be rejected before any runner client is created")

    monkeypatch.setattr("mindx_runner.cli.SupabaseRunnerClient", UnexpectedClient)

    assert main(["preflight"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "error_code": "LIVE_CONFIG_INVALID",
    }


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
async def test_run_job_decrypts_active_browser_state_before_starting_session() -> None:
    class StateClient(FakeClient):
        def load_active_browser_state(self, workspace_id: str, site: str) -> bytes:
            assert workspace_id == WORKSPACE_ID
            assert site == "teaching"
            envelope = BrowserStateCipher(bytes(range(32)), key_version=4).encrypt(
                b'{"cookies":[],"origins":[]}', site="teaching"
            )
            return envelope.to_bytes()

    client = StateClient([])
    session = FakeSession({})
    created_options: dict[str, object] = {}
    observed_state: dict[str, object] = {}

    def session_factory(**options: object) -> FakeSession:
        created_options.update(options)
        observed_state.update(
            json.loads(Path(str(options["storage_state"])).read_text(encoding="utf-8"))
        )
        return session

    async def adapter(*_: object) -> int:
        return 0

    summary = await run_job(
        JOB_ID,
        ENVIRONMENT,
        client_factory=lambda _: client,
        session_factory=session_factory,
        adapter=adapter,
    )

    assert summary.status == "succeeded"
    assert observed_state == {"cookies": [], "origins": []}
    assert not Path(str(created_options["storage_state"])).exists()


@pytest.mark.asyncio
async def test_empty_payload_workspace_mismatch_fails_before_state_read_or_browser(
) -> None:
    other_workspace = "00000000-0000-4000-8000-000000000004"
    target = {**TARGET_DATA, "workspace_id": other_workspace}
    environment = {
        **ENVIRONMENT,
        "MINDX_TEACHING_TARGET_JSON": json.dumps(target, separators=(",", ":")),
    }

    class TrackingClient(FakeClient):
        state_reads = 0

        def load_active_browser_state(self, workspace_id: str, site: str) -> None:
            self.state_reads += 1
            return None

    client = TrackingClient([])
    browser_created = False

    def session_factory(**_: object) -> FakeSession:
        nonlocal browser_created
        browser_created = True
        return FakeSession({})

    async def adapter(*_: object) -> int:
        return 1

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            environment,
            client_factory=lambda _: client,
            session_factory=session_factory,
            adapter=adapter,
        )

    assert error.value.code == "WORKSPACE_ID_MISMATCH"
    assert client.state_reads == 0
    assert browser_created is False
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "WORKSPACE_ID_MISMATCH")


@pytest.mark.asyncio
async def test_nonempty_legacy_payload_ignores_trusted_workspace_target() -> None:
    target = {**TARGET_DATA, "workspace_id": "00000000-0000-4000-8000-000000000004"}
    environment = {
        **ENVIRONMENT,
        "MINDX_TEACHING_TARGET_JSON": json.dumps(target, separators=(",", ":")),
    }
    legacy_payload = {
        "teaching_url": "https://teachingmindx.top/legacy-schedule",
        "allowed_class_codes": ["SYN-LEGACY-01"],
    }

    class LegacyPayloadClient(FakeClient):
        def claim_job_run(self, job_id: str, runner_id: str) -> ClaimedRun:
            claimed = super().claim_job_run(job_id, runner_id)
            return ClaimedRun(
                claimed=True,
                run_id=claimed.run_id,
                job_id=claimed.job_id,
                workspace_id=claimed.workspace_id,
                job_type=claimed.job_type,
                payload=legacy_payload,
                attempt=claimed.attempt,
            )

    client = LegacyPayloadClient([])
    seen_payloads: list[dict[str, object]] = []

    async def adapter(_: object, claimed: ClaimedRun, __: object) -> int:
        seen_payloads.append(claimed.payload)
        return 0

    result = await run_job(
        JOB_ID,
        environment,
        client_factory=lambda _: client,
        session_factory=lambda **_: FakeSession(),
        adapter=adapter,
    )

    assert result.status == "succeeded"
    assert seen_payloads == [legacy_payload]


@pytest.mark.asyncio
async def test_run_job_rejects_active_state_for_an_unapproved_origin() -> None:
    class EvilStateClient(FakeClient):
        def load_active_browser_state(self, workspace_id: str, site: str) -> bytes:
            envelope = BrowserStateCipher(bytes(range(32)), key_version=4).encrypt(
                b'{"cookies":[],"origins":[{"origin":"https://evil.example","localStorage":[]}]}',
                site="teaching",
            )
            return envelope.to_bytes()

    client = EvilStateClient([])
    session_created = False

    def session_factory(**_: object) -> FakeSession:
        nonlocal session_created
        session_created = True
        return FakeSession({})

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=session_factory,
            adapter=lambda *_: asyncio.sleep(0, result=0),
        )

    assert error.value.code == "STORAGE_STATE_INVALID"
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "STORAGE_STATE_INVALID")
    assert session_created is False


@pytest.mark.asyncio
async def test_run_job_finishes_failed_when_active_browser_state_is_missing() -> None:
    class MissingStateClient(FakeClient):
        def load_active_browser_state(self, workspace_id: str, site: str) -> None:
            return None

    client = MissingStateClient([])
    session = FakeSession({})
    session_created = False

    def session_factory(**_: object) -> FakeSession:
        nonlocal session_created
        session_created = True
        return session

    async def adapter(*_: object) -> int:
        return 0

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=session_factory,
            adapter=adapter,
        )

    assert error.value.code == "STORAGE_STATE_DECRYPT_FAILED"
    assert client.finished[0][:4] == (
        RUN_ID,
        "failed",
        0,
        "STORAGE_STATE_DECRYPT_FAILED",
    )
    assert session_created is False


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
async def test_run_job_finishes_known_browser_startup_failure() -> None:
    class FailingStartSession(FakeSession):
        async def start(self) -> None:
            raise RuntimeError("cookie=synthetic-cookie")

    client = FakeClient([])
    session = FailingStartSession({})

    with pytest.raises(BrowserStartupError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=lambda *_: asyncio.sleep(0, result=0),
        )

    assert error.value.code == "BROWSER_STARTUP_FAILED"
    assert client.finished[0][:4] == (
        RUN_ID,
        "failed",
        0,
        "BROWSER_STARTUP_FAILED",
    )
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
@pytest.mark.parametrize(
    "invalid_result",
    [-1, True, False, -99, 1.5, "3", 2_147_483_648],
)
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


@pytest.mark.asyncio
async def test_close_browser_with_bound_skips_when_wall_deadline_expired() -> None:
    from mindx_runner.browser_driver import ReadonlyBrowserSession
    from mindx_runner.cli import _close_browser_with_bound

    close_calls = 0

    class TrackingSession(FakeSession):
        async def stop(self) -> None:
            nonlocal close_calls
            close_calls += 1
            await super().stop()

    session = TrackingSession()
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)
    await browser.start()

    loop = asyncio.get_running_loop()
    past_wall_deadline = loop.time() - 1.0

    start_time = loop.time()
    await _close_browser_with_bound(
        browser,
        wall_deadline=past_wall_deadline,
        cleanup_budget=1.0,
    )
    elapsed = loop.time() - start_time

    assert close_calls == 0
    assert session.closed is False
    assert elapsed < 0.05


@pytest.mark.asyncio
async def test_adapter_cooperative_cancellation_finishes_before_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)

    adapter_finished = False
    adapter_done_at_finalization: bool | None = None

    @dataclass
    class TrackingFinishClient(FakeClient):
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
            nonlocal adapter_done_at_finalization
            adapter_done_at_finalization = adapter_finished
            super().finish_job_run(
                run_id,
                runner_id,
                status,
                records_read=records_read,
                error_code=error_code,
                duration_ms=duration_ms,
            )

    client = TrackingFinishClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        nonlocal adapter_finished
        try:
            await asyncio.Event().wait()
        finally:
            adapter_finished = True
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
    assert adapter_done_at_finalization is True
    assert len(client.finished) == 1
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "RUNNER_TIMEOUT")
    assert session.closed is True


@pytest.mark.asyncio
async def test_adapter_delayed_cancellation_within_grace_completes_before_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)

    adapter_ended_at = 0.0
    finalization_started_at = 0.0

    @dataclass
    class TimingFinishClient(FakeClient):
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
            nonlocal finalization_started_at
            finalization_started_at = time.monotonic()
            super().finish_job_run(
                run_id,
                runner_id,
                status,
                records_read=records_read,
                error_code=error_code,
                duration_ms=duration_ms,
            )

    client = TimingFinishClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        nonlocal adapter_ended_at
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0.003)
            adapter_ended_at = time.monotonic()
            raise
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
    assert adapter_ended_at > 0.0
    assert finalization_started_at >= adapter_ended_at
    assert len(client.finished) == 1
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "RUNNER_TIMEOUT")
    assert session.closed is True


@pytest.mark.asyncio
async def test_adapter_exceeding_cancellation_grace_does_not_hang_or_double_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = FakeClient([])
    session = FakeSession()

    rogue_task: asyncio.Task[Any] | None = None

    async def rogue_adapter(*_: object) -> int:
        nonlocal rogue_task
        rogue_task = asyncio.current_task()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(10)
            raise
        return 2

    try:
        start_time = asyncio.get_running_loop().time()
        with pytest.raises(RunnerError) as error:
            await asyncio.wait_for(
                run_job(
                    JOB_ID,
                    ENVIRONMENT,
                    client_factory=lambda _: client,
                    session_factory=lambda **_: session,
                    adapter=rogue_adapter,
                ),
                timeout=0.3,
            )
        elapsed = asyncio.get_running_loop().time() - start_time

        assert error.value.code == "RUNNER_TIMEOUT"
        assert elapsed < 0.25
        assert len(client.finished) <= 1
        if client.finished:
            assert client.finished[0][:4] == (RUN_ID, "failed", 0, "RUNNER_TIMEOUT")
        assert session.closed is True
    finally:
        if rogue_task is not None and not rogue_task.done():
            rogue_task.cancel()
            with suppress(asyncio.CancelledError):
                await rogue_task


@pytest.mark.asyncio
async def test_browser_cleanup_does_not_overlap_with_cooperative_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = FakeClient([])

    adapter_active = False
    cleanup_started_while_adapter_active = False

    async def adapter(*_: object) -> int:
        nonlocal adapter_active
        adapter_active = True
        try:
            await asyncio.Event().wait()
        finally:
            adapter_active = False
        return 2

    class TrackingSession(FakeSession):
        async def stop(self) -> None:
            nonlocal cleanup_started_while_adapter_active
            if adapter_active:
                cleanup_started_while_adapter_active = True
            await super().stop()

    session = TrackingSession()

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=adapter,
        )

    assert error.value.code == "RUNNER_TIMEOUT"
    assert cleanup_started_while_adapter_active is False
    assert session.closed is True


@pytest.mark.asyncio
async def test_browser_start_timeout_with_slow_cleanup_bounds_execution_within_wall_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = FakeClient([])
    session = SlowStartCleanupSession()

    start_time = asyncio.get_running_loop().time()
    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=lambda *_: 2,
        )
    elapsed = asyncio.get_running_loop().time() - start_time

    assert error.value.code == "RUNNER_TIMEOUT"
    assert client.finished == []
    assert elapsed < 0.14
    assert session.stop_calls <= 1


@pytest.mark.asyncio
async def test_browser_start_normal_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = FakeClient([])
    session = FakeSession()

    async def adapter(*_: object) -> int:
        return 3

    summary = await run_job(
        JOB_ID,
        ENVIRONMENT,
        client_factory=lambda _: client,
        session_factory=lambda **_: session,
        adapter=adapter,
    )

    assert summary.status == "succeeded"
    assert summary.records_read == 3
    assert len(client.finished) == 1
    assert client.finished[0][:4] == (RUN_ID, "succeeded", 3, None)
    assert session.closed is True
    assert session.stop_calls == 1


@pytest.mark.asyncio
async def test_browser_start_timeout_cooperative_cleanup_quick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mindx_runner import cli as cli_module

    monkeypatch.setattr(cli_module, "RUN_TIMEOUT_SECONDS", 0.1)
    client = FakeClient([])
    session = SlowStartSession()

    with pytest.raises(RunnerError) as error:
        await run_job(
            JOB_ID,
            ENVIRONMENT,
            client_factory=lambda _: client,
            session_factory=lambda **_: session,
            adapter=lambda *_: 2,
        )

    assert error.value.code == "RUNNER_TIMEOUT"
    assert client.finished == []
    assert session.closed is True
    assert session.stop_calls == 1


@pytest.mark.asyncio
async def test_browser_start_timeout_when_wall_budget_almost_exhausted() -> None:
    from mindx_runner.browser_driver import ReadonlyBrowserSession
    from mindx_runner.cli import _start_browser_with_bound

    session = FakeSession()
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    loop = asyncio.get_running_loop()
    past_work_deadline = loop.time() - 0.01
    cancellation_deadline = loop.time() + 0.05
    wall_deadline = loop.time() + 0.10

    start_time = loop.time()
    with pytest.raises(RunnerError) as error:
        await _start_browser_with_bound(
            browser,
            work_deadline=past_work_deadline,
            cancellation_deadline=cancellation_deadline,
            wall_deadline=wall_deadline,
        )
    elapsed = loop.time() - start_time

    assert error.value.code == "RUNNER_TIMEOUT"
    assert elapsed < 0.05
