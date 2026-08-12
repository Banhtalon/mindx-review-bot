import base64
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal, NoReturn
from urllib.parse import urlparse
from uuid import UUID

LIVE_CONFIG_INVALID: Final[str] = "LIVE_CONFIG_INVALID"
RUNNER_FAILED: Final[str] = "RUNNER_FAILED"
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
    if not parsed.hostname.endswith(".supabase.co"):
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
        job_type=job_type,  # type: ignore[arg-type]
        supabase_url=_validate_supabase_url(_required(environment, "SUPABASE_URL")),
        supabase_secret_key=_required(environment, "SUPABASE_SECRET_KEY"),
        browser_state_key=_decode_key(_required(environment, "BROWSER_STATE_ENCRYPTION_KEY")),
        teaching_username=_required(environment, "TEACHING_USERNAME"),
        teaching_password=_required(environment, "TEACHING_PASSWORD"),
        lms_username=_required(environment, "LMS_USERNAME"),
        lms_password=_required(environment, "LMS_PASSWORD"),
    )


def safe_error_code(error: BaseException) -> str:
    code = getattr(error, "code", None)
    return code if isinstance(code, str) and code.isupper() else RUNNER_FAILED
