import re

SAFE_ENUM_VALUES: dict[str, frozenset[str]] = {
    "status": frozenset(
        {
            "queued",
            "dispatching",
            "dispatched",
            "running",
            "succeeded",
            "partial",
            "dispatch_failed",
            "failed",
            "cancelled",
        }
    ),
    "jobType": frozenset({"sync_teaching", "read_lms_pending"}),
    "job_type": frozenset({"sync_teaching", "read_lms_pending"}),
    "errorCode": frozenset(
        {
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
            "JOB_LEASE_EXPIRED",
            "GITHUB_DISPATCH_FAILED",
            "SUPABASE_UNAVAILABLE",
            "GEMINI_TIMEOUT",
            "GEMINI_SCHEMA_INVALID",
            "GENERATION_PARTIAL",
            "STORAGE_STATE_DECRYPT_FAILED",
            "QUOTA_GUARD_BLOCKED",
        }
    ),
    "error_code": frozenset(
        {
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
            "JOB_LEASE_EXPIRED",
            "GITHUB_DISPATCH_FAILED",
            "SUPABASE_UNAVAILABLE",
            "GEMINI_TIMEOUT",
            "GEMINI_SCHEMA_INVALID",
            "GENERATION_PARTIAL",
            "STORAGE_STATE_DECRYPT_FAILED",
            "QUOTA_GUARD_BLOCKED",
        }
    ),
}

NUMERIC_KEYS = frozenset(
    {
        "recordsRead",
        "records_read",
        "durationMs",
        "duration_ms",
        "attempt",
        "studentCount",
        "student_count",
        "classCount",
        "class_count",
        "browserMs",
        "browser_ms",
    }
)
ID_KEYS = frozenset({"jobId", "job_id"})
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _sanitize_entry(key: str, value: object) -> object | None:
    if key in ID_KEYS and isinstance(value, str) and UUID_PATTERN.fullmatch(value):
        return value
    if (
        key in NUMERIC_KEYS
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    ):
        return value
    allowed_values = SAFE_ENUM_VALUES.get(key)
    if allowed_values is not None and isinstance(value, str) and value in allowed_values:
        return value
    return None


def sanitize_log_metadata(metadata: dict[str, object]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in metadata.items():
        sanitized = _sanitize_entry(str(key), value)
        if sanitized is not None:
            output[str(key)] = sanitized
    return output
