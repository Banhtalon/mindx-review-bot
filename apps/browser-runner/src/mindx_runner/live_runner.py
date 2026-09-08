import base64
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal, NoReturn
from urllib.parse import urlparse
from uuid import UUID

LIVE_CONFIG_INVALID: Final[str] = "LIVE_CONFIG_INVALID"
RUNNER_FAILED: Final[str] = "RUNNER_FAILED"
SAFE_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        LIVE_CONFIG_INVALID,
        RUNNER_FAILED,
        "AUTH_EXPIRED",
        "AUTH_FAILED",
        "CAPTCHA_DETECTED",
        "DOMAIN_BLOCKED",
        "TEACHING_SELECTOR_CHANGED",
        "LMS_SELECTOR_CHANGED",
        "CLASS_IDENTITY_MISMATCH",
        "SESSION_IDENTITY_MISMATCH",
        "STUDENT_MAPPING_UNRESOLVABLE",
        "PRIVACY_GUARD_BLOCKED",
        "JOB_ALREADY_CLAIMED",
        "JOB_TYPE_MISMATCH",
        "JOB_LEASE_EXPIRED",
        "JOB_MAX_ATTEMPTS_EXCEEDED",
        "JOB_RUNNER_MISMATCH",
        "JOB_NOT_READY",
        "RUNNER_ID_INVALID",
        "SUPABASE_UNAVAILABLE",
        "STORAGE_STATE_DECRYPT_FAILED",
        "STORAGE_PATH_INVALID",
        "BROWSER_NETWORK_GUARD_UNAVAILABLE",
        "QUOTA_GUARD_BLOCKED",
        "RUNNER_RESULT_INVALID",
        "SITE_ADAPTER_NOT_CONFIGURED",
        "RUNNER_TIMEOUT",
        "HOSTED_PROBE_CANCELLED",
    }
)
JobType = Literal["sync_teaching", "read_lms_pending"]


class LiveConfigError(RuntimeError):
    def __init__(self, field_name: str | None = None) -> None:
        self.code = LIVE_CONFIG_INVALID
        self.field_name = field_name
        message = (
            LIVE_CONFIG_INVALID
            if field_name is None
            else f"{LIVE_CONFIG_INVALID}:{field_name}"
        )
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class LiveRunConfig:
    job_id: str
    runner_id: str
    job_type: JobType
    supabase_url: str
    supabase_secret_key: str = field(repr=False)
    browser_state_key: bytes = field(repr=False)
    teaching_username: str = field(repr=False)
    teaching_password: str = field(repr=False)
    lms_username: str = field(repr=False)
    lms_password: str = field(repr=False)


def _fail(field_name: str | None = None) -> NoReturn:
    raise LiveConfigError(field_name)


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or value == "":
        _fail(name)
    return value


def _flag(environment: Mapping[str, str], name: str, expected: str) -> None:
    if _required(environment, name).lower() != expected:
        _fail(name)


def validate_job_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        _fail("JOB_ID")
    canonical = str(parsed)
    if value.lower() != canonical:
        _fail("JOB_ID")
    return canonical


def validate_runner_id(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}", value) is None:
        _fail("RUNNER_ID")
    return value


def _decode_key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError):
        _fail("BROWSER_STATE_ENCRYPTION_KEY")
    if len(decoded) != 32:
        _fail("BROWSER_STATE_ENCRYPTION_KEY")
    return decoded


def _validate_supabase_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname is None:
        _fail("SUPABASE_URL")
    if not parsed.hostname.endswith(".supabase.co") or parsed.hostname.count(".") != 2:
        _fail("SUPABASE_URL")
    try:
        port = parsed.port
    except ValueError:
        _fail("SUPABASE_URL")
    if (
        parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        _fail("SUPABASE_URL")
    return value.rstrip("/")


def load_live_config(environment: Mapping[str, str]) -> LiveRunConfig:
    _flag(environment, "AUTOMATION_ENABLED", "true")
    _flag(environment, "MVP_LMS_WRITE_ENABLED", "false")

    job_type = _required(environment, "JOB_TYPE")
    if job_type not in {"sync_teaching", "read_lms_pending"}:
        _fail("JOB_TYPE")

    return LiveRunConfig(
        job_id=validate_job_id(_required(environment, "JOB_ID")),
        runner_id=validate_runner_id(_required(environment, "RUNNER_ID")),
        job_type=job_type,  # type: ignore[arg-type]
        supabase_url=_validate_supabase_url(_required(environment, "SUPABASE_URL")),
        **{"supabase_secret_key": _required(environment, "SUPABASE_SECRET_KEY")},
        browser_state_key=_decode_key(_required(environment, "BROWSER_STATE_ENCRYPTION_KEY")),
        teaching_username=(
            _required(environment, "TEACHING_USERNAME")
            if job_type == "sync_teaching"
            else ""
        ),
        teaching_password=(
            _required(environment, "TEACHING_PASSWORD")
            if job_type == "sync_teaching"
            else ""
        ),
        lms_username=(
            _required(environment, "LMS_USERNAME")
            if job_type == "read_lms_pending"
            else ""
        ),
        lms_password=(
            _required(environment, "LMS_PASSWORD")
            if job_type == "read_lms_pending"
            else ""
        ),
    )


def safe_error_code(error: BaseException) -> str:
    code = getattr(error, "code", None)
    return code if isinstance(code, str) and code in SAFE_ERROR_CODES else RUNNER_FAILED
