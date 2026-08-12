import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from .browser_state import ALLOWED_STATE_SITES, ObjectStore

SUPABASE_UNAVAILABLE: Final[str] = "SUPABASE_UNAVAILABLE"
RUNNER_RESULT_INVALID: Final[str] = "RUNNER_RESULT_INVALID"
STORAGE_PATH_INVALID: Final[str] = "STORAGE_PATH_INVALID"
ALLOWED_RUN_STATUSES = frozenset({"succeeded", "partial", "failed", "cancelled"})
SAFE_ERROR_CODES = frozenset(
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
        "JOB_TYPE_MISMATCH",
        "JOB_LEASE_EXPIRED",
        "LIVE_CONFIG_INVALID",
        "SUPABASE_UNAVAILABLE",
        "STORAGE_STATE_DECRYPT_FAILED",
        "STORAGE_PATH_INVALID",
        "BROWSER_NETWORK_GUARD_UNAVAILABLE",
        "QUOTA_GUARD_BLOCKED",
        "RUNNER_RESULT_INVALID",
        "SITE_ADAPTER_NOT_CONFIGURED",
        "RUNNER_FAILED",
    }
)
JobType = Literal["sync_teaching", "read_lms_pending"]


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes = field(repr=False)


class HttpTransport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> HttpResponse:
        ...


def _default_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
) -> HttpResponse:
    request = Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return HttpResponse(response.status, response.read())
    except HTTPError as error:
        return HttpResponse(error.code, b"")
    except (OSError, URLError) as error:
        raise SupabaseClientError(SUPABASE_UNAVAILABLE) from error


class SupabaseClientError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ClaimedRun:
    claimed: bool
    run_id: str
    job_id: str
    workspace_id: str
    job_type: JobType
    payload: dict[str, object]
    attempt: int


def _uuid(value: str, field_name: str) -> str:
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise SupabaseClientError(f"{RUNNER_RESULT_INVALID}:{field_name}") from error
    return str(parsed)


def _json_body(value: object) -> bytes:
    try:
        return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SupabaseClientError(RUNNER_RESULT_INVALID) from error


def _json_value(body: bytes) -> object:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SupabaseClientError(SUPABASE_UNAVAILABLE) from error


def _object_path(path: str, bucket: str) -> str:
    prefix = f"{bucket}/"
    state_path = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    if (
        not path.startswith(prefix)
        or "\\" in path
        or "\x00" in path
        or any(part in {"", ".", ".."} for part in path[len(prefix) :].split("/"))
        or re.fullmatch(
            rf"{re.escape(bucket)}/{state_path}/(?:teaching|lms)/{state_path}\.json",
            path,
        ) is None
    ):
        raise SupabaseClientError(STORAGE_PATH_INVALID)
    return path[len(prefix) :]


class SupabaseStorageObjectStore(ObjectStore):
    def __init__(self, client: "SupabaseRunnerClient") -> None:
        self._client = client

    def put(self, path: str, value: bytes) -> None:
        storage_path = _object_path(path, self._client.bucket)
        response = self._client._request(
            "POST",
            f"/storage/v1/object/{self._client.bucket}/{quote(storage_path, safe='/')}",
            value,
            content_type="application/json",
        )
        self._client._require_success(response)

    def get(self, path: str) -> bytes:
        storage_path = _object_path(path, self._client.bucket)
        response = self._client._request(
            "GET",
            f"/storage/v1/object/{self._client.bucket}/{quote(storage_path, safe='/')}",
            None,
        )
        if response.status == 404:
            raise KeyError(path)
        self._client._require_success(response)
        return response.body

    def delete(self, path: str) -> None:
        storage_path = _object_path(path, self._client.bucket)
        response = self._client._request(
            "DELETE",
            f"/storage/v1/object/{self._client.bucket}",
            _json_body({"prefixes": [storage_path]}),
            content_type="application/json",
        )
        self._client._require_success(response)


class SupabaseRunnerClient:
    def __init__(
        self,
        base_url: str,
        secret_key: str,
        *,
        transport: HttpTransport = _default_transport,
        bucket: str = "browser-state",
    ) -> None:
        parsed = urlparse(base_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or not parsed.hostname.endswith(".supabase.co")
            or not secret_key
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,62}", bucket) is None
        ):
            raise SupabaseClientError(RUNNER_RESULT_INVALID)
        self.base_url = base_url.rstrip("/")
        self._secret_key = secret_key
        self._transport = transport
        self.bucket = bucket
        self.object_store = SupabaseStorageObjectStore(self)

    def __repr__(self) -> str:
        return f"SupabaseRunnerClient(base_url={self.base_url!r}, bucket={self.bucket!r})"

    def _request(
        self,
        method: str,
        path: str,
        body: bytes | None,
        *,
        content_type: str | None = None,
    ) -> HttpResponse:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._secret_key}",
            "apikey": self._secret_key,
        }
        if content_type is not None:
            headers["Content-Type"] = content_type
        return self._transport(method, f"{self.base_url}{path}", headers, body)

    @staticmethod
    def _require_success(response: HttpResponse) -> None:
        if response.status < 200 or response.status >= 300:
            raise SupabaseClientError(SUPABASE_UNAVAILABLE)

    def _rpc(self, name: str, payload: Mapping[str, object]) -> object:
        response = self._request(
            "POST",
            f"/rest/v1/rpc/{name}",
            _json_body(payload),
            content_type="application/json",
        )
        self._require_success(response)
        return _json_value(response.body)

    def claim_job_run(self, job_id: str) -> ClaimedRun:
        target_job_id = _uuid(job_id, "job_id")
        raw = self._rpc("claim_automation_job_run", {"target_job_id": target_job_id})
        if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
            raise SupabaseClientError(SUPABASE_UNAVAILABLE)
        row = cast(dict[str, Any], raw[0])
        claimed = row.get("claimed")
        job_type = row.get("job_type")
        payload = row.get("payload_json")
        if (
            not isinstance(claimed, bool)
            or not isinstance(job_type, str)
            or job_type not in {"sync_teaching", "read_lms_pending"}
            or not isinstance(payload, dict)
            or not isinstance(row.get("attempt"), int)
        ):
            raise SupabaseClientError(SUPABASE_UNAVAILABLE)
        return ClaimedRun(
            claimed=claimed,
            run_id=_uuid(str(row.get("run_id")), "run_id"),
            job_id=_uuid(str(row.get("job_id")), "job_id"),
            workspace_id=_uuid(str(row.get("workspace_id")), "workspace_id"),
            job_type=cast(JobType, job_type),
            payload=cast(dict[str, object], payload),
            attempt=row["attempt"],
        )

    def finish_job_run(
        self,
        run_id: str,
        status: str,
        *,
        records_read: int,
        error_code: str | None,
    ) -> None:
        target_run_id = _uuid(run_id, "run_id")
        if (
            status not in ALLOWED_RUN_STATUSES
            or isinstance(records_read, bool)
            or records_read < 0
            or error_code is not None
            and error_code not in SAFE_ERROR_CODES
        ):
            raise SupabaseClientError("RUNNER_RESULT_INVALID")
        raw = self._rpc(
            "finish_automation_job_run",
            {
                "target_run_id": target_run_id,
                "target_status": status,
                "target_records_read": records_read,
                "target_error_code": error_code,
            },
        )
        if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
            raise SupabaseClientError(SUPABASE_UNAVAILABLE)

    def activate_browser_state_version(
        self,
        workspace_id: str,
        site: str,
        version_id: str,
        object_path: str,
        key_version: int,
        state_hash: str,
    ) -> None:
        workspace = _uuid(workspace_id, "workspace_id")
        version = _uuid(version_id, "version_id")
        if site not in ALLOWED_STATE_SITES or not isinstance(key_version, int) or key_version < 1:
            raise SupabaseClientError(RUNNER_RESULT_INVALID)
        if len(state_hash) != 64 or any(
            char not in "0123456789abcdef" for char in state_hash.lower()
        ):
            raise SupabaseClientError(RUNNER_RESULT_INVALID)
        _object_path(object_path, self.bucket)
        raw = self._rpc(
            "activate_browser_state_version",
            {
                "target_workspace_id": workspace,
                "target_site": site,
                "target_version_id": version,
                "target_object_path": object_path,
                "target_key_version": key_version,
                "target_state_hash": state_hash,
            },
        )
        if not isinstance(raw, list) or len(raw) != 1:
            raise SupabaseClientError(SUPABASE_UNAVAILABLE)

    def reset_browser_state(self, workspace_id: str, site: str) -> str | None:
        workspace = _uuid(workspace_id, "workspace_id")
        if site not in ALLOWED_STATE_SITES:
            raise SupabaseClientError(RUNNER_RESULT_INVALID)
        raw = self._rpc(
            "reset_browser_state",
            {"target_workspace_id": workspace, "target_site": site},
        )
        if raw == []:
            return None
        if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
            raise SupabaseClientError(SUPABASE_UNAVAILABLE)
        path = raw[0].get("object_path")
        if not isinstance(path, str):
            raise SupabaseClientError(SUPABASE_UNAVAILABLE)
        _object_path(path, self.bucket)
        return path
