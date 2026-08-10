from collections.abc import Mapping

SAFE_KEYS = frozenset(
    {
        "jobId",
        "job_id",
        "jobType",
        "job_type",
        "status",
        "recordsRead",
        "records_read",
        "errorCode",
        "error_code",
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


def _sanitize(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize(nested)
            for key, nested in value.items()
            if str(key) in SAFE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def sanitize_log_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return _sanitize(metadata)  # type: ignore[return-value]
