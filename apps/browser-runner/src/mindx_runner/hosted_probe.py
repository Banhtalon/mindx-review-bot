import argparse
import base64
import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from functools import partial
from typing import Protocol
from urllib.parse import urlparse
from uuid import UUID

from .browser_state import BrowserStateCipher, EncryptedStateEnvelope, ObjectStore
from .supabase_client import (
    BrowserStateRecord,
    ClaimedRun,
    EnqueuedProbeJob,
    SupabaseClientError,
    SupabaseRunnerClient,
)

SYNTHETIC_STATE = b'{"kind":"phase2-hosted-probe","schema":1}'
KEY_VERSION = 1


class HostedProbeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class HostedProbeConfig:
    probe_id: str
    workspace_id: str
    site: str
    encryption_key: bytes
    requested_by: str = ""

    @property
    def object_path(self) -> str:
        return (
            f"browser-state/{self.workspace_id}/{self.site}/{self.probe_id}.json"
        )

    @property
    def idempotency_key(self) -> str:
        return f"phase2-probe:{self.probe_id}"


@dataclass(frozen=True, slots=True)
class HostedProbeSummary:
    status: str
    version_id: str
    state_hash: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class DatabaseProbeSummary:
    status: str
    job_id: str
    attempts: int
    duplicate_claim_blocked: bool
    wrong_runner_blocked: bool
    role_boundary_checks: int


class HostedStateClient(Protocol):
    @property
    def object_store(self) -> ObjectStore:
        ...

    def get_active_browser_state(
        self, workspace_id: str, site: str
    ) -> BrowserStateRecord | None:
        ...

    def activate_browser_state_version(
        self,
        workspace_id: str,
        site: str,
        version_id: str,
        object_path: str,
        key_version: int,
        state_hash: str,
    ) -> None:
        ...

    def reset_browser_state(self, workspace_id: str, site: str) -> str | None:
        ...

    def delete_probe_rows(self, version_id: str, idempotency_key: str) -> None:
        ...


class HostedDatabaseClient(Protocol):
    def enqueue_probe_job(
        self, workspace_id: str, requested_by: str, probe_id: str
    ) -> EnqueuedProbeJob:
        ...

    def claim_job_dispatch(self, job_id: str) -> bool:
        ...

    def finish_job_dispatch(self, job_id: str) -> None:
        ...

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

    def expire_probe_lease(self, job_id: str) -> None:
        ...

def _expected_hash() -> str:
    return hashlib.sha256(SYNTHETIC_STATE).hexdigest()


def _cipher(config: HostedProbeConfig) -> BrowserStateCipher:
    return BrowserStateCipher(config.encryption_key, KEY_VERSION)


def _expect_denied(operation: Callable[[], object]) -> None:
    try:
        operation()
    except (SupabaseClientError, OSError):
        return
    raise HostedProbeError("HOSTED_PROBE_ROLE_BOUNDARY_FAILED")


def run_database_probe(
    config: HostedProbeConfig,
    client: HostedDatabaseClient,
    denied_clients: Sequence[HostedDatabaseClient] = (),
) -> DatabaseProbeSummary:
    if not config.requested_by:
        raise HostedProbeError("HOSTED_PROBE_CONFIG_INVALID")
    job = client.enqueue_probe_job(
        config.workspace_id,
        config.requested_by,
        config.probe_id,
    )
    if not job.created:
        raise HostedProbeError("HOSTED_PROBE_NOT_ISOLATED")
    if job.status == "queued":
        if not client.claim_job_dispatch(job.job_id):
            raise HostedProbeError("HOSTED_PROBE_DATABASE_MISMATCH")
        client.finish_job_dispatch(job.job_id)
    elif job.status != "dispatched":
        raise HostedProbeError("HOSTED_PROBE_NOT_ISOLATED")

    role_checks = 0
    for denied_client in denied_clients:
        _expect_denied(partial(denied_client.claim_job_run, job.job_id, "probe-denied"))
        role_checks += 1

    runner_one = f"phase2-{config.probe_id[:8]}-1"
    runner_two = f"phase2-{config.probe_id[:8]}-2"
    runner_three = f"phase2-{config.probe_id[:8]}-3"
    first = client.claim_job_run(job.job_id, runner_one)
    if not first.claimed or first.attempt != 1:
        raise HostedProbeError("HOSTED_PROBE_DATABASE_MISMATCH")
    duplicate = client.claim_job_run(job.job_id, runner_two)
    if duplicate.claimed or duplicate.run_id != first.run_id:
        raise HostedProbeError("HOSTED_PROBE_DATABASE_MISMATCH")
    client.heartbeat_job(job.job_id, runner_one)
    _expect_denied(lambda: client.heartbeat_job(job.job_id, runner_two))
    _expect_denied(
        lambda: client.finish_job_run(
            first.run_id,
            runner_two,
            "failed",
            records_read=0,
            error_code="HOSTED_PROBE_CANCELLED",
        )
    )
    client.finish_job_run(
        first.run_id,
        runner_one,
        "failed",
        records_read=0,
        error_code="HOSTED_PROBE_CANCELLED",
    )

    second = client.claim_job_run(job.job_id, runner_two)
    if not second.claimed or second.attempt != 2:
        raise HostedProbeError("HOSTED_PROBE_DATABASE_MISMATCH")
    client.expire_probe_lease(job.job_id)
    third = client.claim_job_run(job.job_id, runner_three)
    if not third.claimed or third.attempt != 3:
        raise HostedProbeError("HOSTED_PROBE_DATABASE_MISMATCH")
    client.finish_job_run(
        third.run_id,
        runner_three,
        "failed",
        records_read=0,
        error_code="HOSTED_PROBE_CANCELLED",
    )
    _expect_denied(lambda: client.claim_job_run(job.job_id, runner_one))

    return DatabaseProbeSummary(
        status="database_pass",
        job_id=job.job_id,
        attempts=3,
        duplicate_claim_blocked=True,
        wrong_runner_blocked=True,
        role_boundary_checks=role_checks,
    )


def persist_state(
    config: HostedProbeConfig,
    client: HostedStateClient,
) -> HostedProbeSummary:
    if client.get_active_browser_state(config.workspace_id, config.site) is not None:
        raise HostedProbeError("HOSTED_PROBE_NOT_ISOLATED")

    envelope = _cipher(config).encrypt(SYNTHETIC_STATE, site=config.site)
    encrypted = envelope.to_bytes()
    client.object_store.put(config.object_path, encrypted)
    try:
        client.activate_browser_state_version(
            config.workspace_id,
            config.site,
            config.probe_id,
            config.object_path,
            KEY_VERSION,
            envelope.state_hash,
        )
    except BaseException:
        try:
            client.object_store.delete(config.object_path)
        except BaseException:
            pass
        raise
    return HostedProbeSummary(
        status="persisted",
        version_id=config.probe_id,
        state_hash=envelope.state_hash,
        byte_count=len(encrypted),
    )


def reuse_and_reset_state(
    config: HostedProbeConfig,
    client: HostedStateClient,
) -> HostedProbeSummary:
    active = client.get_active_browser_state(config.workspace_id, config.site)
    if (
        active is None
        or active.version_id != config.probe_id
        or active.workspace_id != config.workspace_id
        or active.site != config.site
        or active.object_path != config.object_path
        or active.key_version != KEY_VERSION
        or active.state_hash != _expected_hash()
        or active.status != "active"
    ):
        raise HostedProbeError("HOSTED_PROBE_STATE_MISMATCH")

    encrypted = client.object_store.get(active.object_path)
    plaintext = _cipher(config).decrypt(
        EncryptedStateEnvelope.from_bytes(encrypted),
        site=config.site,
    )
    if plaintext != SYNTHETIC_STATE:
        raise HostedProbeError("HOSTED_PROBE_STATE_MISMATCH")

    reset_path = client.reset_browser_state(config.workspace_id, config.site)
    if reset_path != config.object_path:
        raise HostedProbeError("HOSTED_PROBE_STATE_MISMATCH")
    client.object_store.delete(reset_path)
    if client.reset_browser_state(config.workspace_id, config.site) is not None:
        raise HostedProbeError("HOSTED_PROBE_STATE_MISMATCH")
    if client.get_active_browser_state(config.workspace_id, config.site) is not None:
        raise HostedProbeError("HOSTED_PROBE_STATE_MISMATCH")
    try:
        client.object_store.get(config.object_path)
    except KeyError:
        pass
    else:
        raise HostedProbeError("HOSTED_PROBE_STATE_MISMATCH")

    return HostedProbeSummary(
        status="reset",
        version_id=config.probe_id,
        state_hash=_expected_hash(),
        byte_count=len(encrypted),
    )


def cleanup_probe(
    config: HostedProbeConfig,
    client: HostedStateClient,
) -> HostedProbeSummary:
    last_error: BaseException | None = None
    for _ in range(2):
        try:
            active = client.get_active_browser_state(config.workspace_id, config.site)
            if active is not None and active.version_id == config.probe_id:
                client.reset_browser_state(config.workspace_id, config.site)
            try:
                client.object_store.delete(config.object_path)
            except KeyError:
                pass
            client.delete_probe_rows(config.probe_id, config.idempotency_key)
            break
        except (OSError, SupabaseClientError) as error:
            last_error = error
    else:
        raise HostedProbeError("HOSTED_PROBE_CLEANUP_FAILED") from last_error
    return HostedProbeSummary(
        status="cleaned",
        version_id=config.probe_id,
        state_hash=_expected_hash(),
        byte_count=0,
    )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or value == "":
        raise HostedProbeError("HOSTED_PROBE_CONFIG_INVALID")
    return value


def _uuid(value: str) -> str:
    try:
        canonical = str(UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise HostedProbeError("HOSTED_PROBE_CONFIG_INVALID") from error
    if canonical != value.lower():
        raise HostedProbeError("HOSTED_PROBE_CONFIG_INVALID")
    return canonical


def _key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as error:
        raise HostedProbeError("HOSTED_PROBE_CONFIG_INVALID") from error
    if len(decoded) != 32:
        raise HostedProbeError("HOSTED_PROBE_CONFIG_INVALID")
    return decoded


def _url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or not parsed.hostname.endswith(".supabase.co")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise HostedProbeError("HOSTED_PROBE_CONFIG_INVALID")
    return value.rstrip("/")


def load_probe_config(
    environment: Mapping[str, str],
    *,
    require_actor: bool,
) -> HostedProbeConfig:
    site = environment.get("PHASE2_SITE", "lms")
    if site not in {"teaching", "lms"}:
        raise HostedProbeError("HOSTED_PROBE_CONFIG_INVALID")
    return HostedProbeConfig(
        probe_id=_uuid(_required(environment, "PHASE2_PROBE_ID")),
        workspace_id=_uuid(_required(environment, "PHASE2_WORKSPACE_ID")),
        site=site,
        encryption_key=_key(_required(environment, "BROWSER_STATE_ENCRYPTION_KEY")),
        requested_by=(
            _uuid(_required(environment, "PHASE2_REQUESTED_BY")) if require_actor else ""
        ),
    )


def _client(environment: Mapping[str, str]) -> SupabaseRunnerClient:
    return SupabaseRunnerClient(
        _url(_required(environment, "SUPABASE_URL")),
        _required(environment, "SUPABASE_SECRET_KEY"),
    )


def _denied_clients(environment: Mapping[str, str]) -> tuple[SupabaseRunnerClient, ...]:
    url = _url(_required(environment, "SUPABASE_URL"))
    anon_key = _required(environment, "SUPABASE_ANON_KEY")
    authenticated_token = _required(environment, "PHASE2_AUTHENTICATED_JWT")
    anon_client = SupabaseRunnerClient(url, anon_key)
    authenticated_client = SupabaseRunnerClient(
        url,
        anon_key,
        authorization_token=authenticated_token,
    )
    authenticated_client.verify_authenticated_identity()
    return (anon_client, authenticated_client)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phase2-hosted-probe")
    parser.add_argument(
        "command",
        choices=("database", "state-persist", "state-reuse-reset", "cleanup"),
    )
    return parser


def _safe_error_code(error: BaseException) -> str:
    allowed = {
        "HOSTED_PROBE_CONFIG_INVALID",
        "HOSTED_PROBE_CLEANUP_FAILED",
        "HOSTED_PROBE_DATABASE_MISMATCH",
        "HOSTED_PROBE_NOT_ISOLATED",
        "HOSTED_PROBE_ROLE_BOUNDARY_FAILED",
        "HOSTED_PROBE_STATE_MISMATCH",
        "RUNNER_RESULT_INVALID",
        "STORAGE_PATH_INVALID",
        "STORAGE_STATE_DECRYPT_FAILED",
        "SUPABASE_UNAVAILABLE",
    }
    code = getattr(error, "code", None)
    return code if isinstance(code, str) and code in allowed else "HOSTED_PROBE_FAILED"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    environment = dict(os.environ)
    try:
        config = load_probe_config(environment, require_actor=args.command == "database")
        client = _client(environment)
        if args.command == "database":
            summary: HostedProbeSummary | DatabaseProbeSummary = run_database_probe(
                config,
                client,
                _denied_clients(environment),
            )
        elif args.command == "state-persist":
            summary = persist_state(config, client)
        elif args.command == "state-reuse-reset":
            summary = reuse_and_reset_state(config, client)
        else:
            summary = cleanup_probe(config, client)
        print(json.dumps(asdict(summary), separators=(",", ":"), sort_keys=True))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {"error_code": _safe_error_code(error), "status": "failed"},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
