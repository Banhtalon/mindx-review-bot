"""Bounded role and existing-job probe helpers; CLI stays fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "apps" / "browser-runner" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "browser-runner" / "src"))

from mindx_runner.supabase_client import HttpResponse  # noqa: E402

PROJECT_REF = "gnvzjvgfsxfjgldatbwt"
BASE_URL = f"https://{PROJECT_REF}.supabase.co"
REPOSITORY = "Banhtalon/mindx-review-bot"
WORKSPACE_ID = "50318d02-6840-457d-b5a6-0870e7a308a4"
WORKSPACE_NAME = "phase2-api-chain-synthetic-20261006-r1"
JOB_ID = "a3fed449-7fac-422f-a3a7-9b22be678c12"
JOB_TYPE = "sync_teaching"
IDEMPOTENCY_KEY = "phase2-api-chain-20261006-r1"
RUNNER_ID = "api-chain-synthetic-r1"
RUN_ID = "ce2d8c98-bd56-5e33-99de-8ef487e4a2ab"
PAYLOAD = {"synthetic": True, "pilot_id": IDEMPOTENCY_KEY, "case": "success"}
ROLES = ("anonymous", "nonmember", "reviewer", "owner")
ROLE_CAPS = {"anonymous": 2, "nonmember": 2, "reviewer": 5, "owner": 6}
ROLE_TOTAL_CAP = 15
NEGATIVE_EDGE_CAP = 3
POSITIVE_EDGE_CAP = 1
TOTAL_SEND_CAP = ROLE_TOTAL_CAP + NEGATIVE_EDGE_CAP + POSITIVE_EDGE_CAP
WORKSPACE_PATH = f"/rest/v1/workspaces?id=eq.{WORKSPACE_ID}&select=id,name&limit=2"
JOB_SELECT = (
    "id,workspace_id,type,status,idempotency_key,requested_by,payload_json,max_attempts,"
    "attempt_count,runner_id,lease_expires_at,heartbeat_at"
)
JOB_GET_PATH = (
    f"/rest/v1/automation_jobs?id=eq.{JOB_ID}"
    f"&workspace_id=eq.{WORKSPACE_ID}&select={JOB_SELECT}&limit=2"
)
JOB_INSERT_PATH = f"/rest/v1/automation_jobs?select={JOB_SELECT}"
EDGE_PATH = "/functions/v1/dispatch-job"
EDGE_BODY = {
    "workspace_id": WORKSPACE_ID,
    "type": JOB_TYPE,
    "idempotency_key": IDEMPOTENCY_KEY,
    "payload": PAYLOAD,
}
_CALLER = "$AUTH_USER_ID"
_RPC_DENIALS = (
    {
        "method": "POST",
        "path": "/rest/v1/rpc/claim_automation_job_run",
        "body": {"target_job_id": JOB_ID, "target_runner_id": RUNNER_ID},
        "expected": "denied",
    },
    {
        "method": "POST",
        "path": "/rest/v1/rpc/heartbeat_automation_job",
        "body": {"target_job_id": JOB_ID, "target_runner_id": RUNNER_ID},
        "expected": "denied",
    },
    {
        "method": "POST",
        "path": "/rest/v1/rpc/finish_automation_job_run",
        "body": {
            "target_run_id": RUN_ID,
            "target_runner_id": RUNNER_ID,
            "target_status": "succeeded",
            "target_records_read": 0,
            "target_error_code": None,
            "target_duration_ms": 0,
        },
        "expected": "denied",
    },
)
_JOB_INSERT = {
    "id": JOB_ID,
    "workspace_id": WORKSPACE_ID,
    "type": JOB_TYPE,
    "status": "queued",
    "idempotency_key": IDEMPOTENCY_KEY,
    "requested_by": _CALLER,
    "payload_json": PAYLOAD,
    "max_attempts": 1,
}
_AUTH_ERROR_CODES = {"AUTH_REQUIRED", "AUTH_FAILED", "PGRST301", "PGRST302"}
_DENIAL_CODES = _AUTH_ERROR_CODES | {"42501", "OWNER_REQUIRED"}
MAX_RESPONSE_BYTES = 8192


class TargetProfile(NamedTuple):
    name: str
    workspace_id: str
    workspace_name: str
    job_id: str
    job_type: str
    idempotency_key: str
    runner_id: str
    run_id: str
    role_cap_items: tuple[tuple[str, int], ...]
    role_total_cap: int
    edge_negative_cap: int
    edge_positive_cap: int
    max_attempts: int

    @property
    def role_caps(self) -> dict[str, int]:
        return dict(self.role_cap_items)

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(role for role, _ in self.role_cap_items)

    @property
    def total_send_cap(self) -> int:
        return self.role_total_cap + self.edge_negative_cap + self.edge_positive_cap

    @property
    def payload(self) -> dict[str, object]:
        return {"synthetic": True, "pilot_id": self.idempotency_key, "case": "success"}


LEGACY_PROFILE = TargetProfile(
    "LEGACY",
    WORKSPACE_ID,
    WORKSPACE_NAME,
    JOB_ID,
    JOB_TYPE,
    IDEMPOTENCY_KEY,
    RUNNER_ID,
    RUN_ID,
    (("anonymous", 2), ("nonmember", 2), ("reviewer", 5), ("owner", 6)),
    ROLE_TOTAL_CAP,
    NEGATIVE_EDGE_CAP,
    POSITIVE_EDGE_CAP,
    1,
)
FRESH_R13_PROFILE = TargetProfile(
    "FRESH_R13",
    "7f2e4996-893e-59e6-9833-5b089d519530",
    "phase2-api-chain-synthetic-20261009-r13",
    "c8841b3c-5740-5b0a-aeaf-9dad5f5f17a5",
    "sync_teaching",
    "phase2-api-chain-20261009-r13",
    "api-chain-synthetic-r13",
    "6ba400ed-2edd-5497-8348-930c382d1123",
    (("anonymous", 2), ("nonmember", 2), ("reviewer", 5), ("owner", 6)),
    15,
    3,
    1,
    1,
)
TARGET_PROFILES = (LEGACY_PROFILE, FRESH_R13_PROFILE)


class OperatorBlocked(RuntimeError):
    """A frozen operator scope or request allowance was exceeded."""


def require_target_profile(profile: object) -> TargetProfile:
    if profile is LEGACY_PROFILE or profile is FRESH_R13_PROFILE:
        return profile
    raise OperatorBlocked("OPERATOR_PROFILE_OUT_OF_SCOPE")


def profile_for_job_id(job_id: object) -> TargetProfile:
    if type(job_id) is str:
        if job_id == LEGACY_PROFILE.job_id:
            return LEGACY_PROFILE
        if job_id == FRESH_R13_PROFILE.job_id:
            return FRESH_R13_PROFILE
    raise OperatorBlocked("OPERATOR_PROFILE_OUT_OF_SCOPE")


def target_scope_manifest(profile: TargetProfile = LEGACY_PROFILE) -> dict[str, object]:
    profile = require_target_profile(profile)
    return {
        "profile": profile.name,
        "workspace": {"id": profile.workspace_id, "name": profile.workspace_name},
        "job": {
            "id": profile.job_id,
            "type": profile.job_type,
            "idempotency_key": profile.idempotency_key,
            "runner_id": profile.runner_id,
            "payload": profile.payload,
            "max_attempts": profile.max_attempts,
        },
        "negative_probe_run_id": profile.run_id,
    }


def profile_budget_caps(profile: TargetProfile = LEGACY_PROFILE) -> dict[str, object]:
    profile = require_target_profile(profile)
    return {
        "role_total": profile.role_total_cap,
        "role_by_name": profile.role_caps,
        "edge_negative": profile.edge_negative_cap,
        "edge_positive": profile.edge_positive_cap,
        "total": profile.total_send_cap,
    }


def profile_scope_digest(profile: TargetProfile = LEGACY_PROFILE) -> str:
    material = {
        "target": target_scope_manifest(profile),
        "budget_caps": profile_budget_caps(profile),
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _copy(value):
    return json.loads(json.dumps(value))


def _valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value) is not None


def _workspace_path(profile: TargetProfile) -> str:
    return f"/rest/v1/workspaces?id=eq.{profile.workspace_id}&select=id,name&limit=2"


def _job_get_path(profile: TargetProfile) -> str:
    return (
        f"/rest/v1/automation_jobs?id=eq.{profile.job_id}"
        f"&workspace_id=eq.{profile.workspace_id}&select={JOB_SELECT}&limit=2"
    )


def _job_insert_path() -> str:
    return f"/rest/v1/automation_jobs?select={JOB_SELECT}"


def _job_insert(profile: TargetProfile) -> dict[str, object]:
    if profile is LEGACY_PROFILE:
        return _copy(_JOB_INSERT)
    return {
        "id": profile.job_id,
        "workspace_id": profile.workspace_id,
        "type": profile.job_type,
        "status": "queued",
        "idempotency_key": profile.idempotency_key,
        "requested_by": _CALLER,
        "payload_json": profile.payload,
        "max_attempts": profile.max_attempts,
    }


def _edge_body(profile: TargetProfile) -> dict[str, object]:
    if profile is LEGACY_PROFILE:
        return EDGE_BODY
    return {
        "workspace_id": profile.workspace_id,
        "type": profile.job_type,
        "idempotency_key": profile.idempotency_key,
        "payload": profile.payload,
    }


def _rpc_denials(profile: TargetProfile) -> list[dict[str, object]]:
    if profile is LEGACY_PROFILE:
        return _copy(_RPC_DENIALS)
    return [
        {
            "method": "POST",
            "path": "/rest/v1/rpc/claim_automation_job_run",
            "body": {
                "target_job_id": profile.job_id,
                "target_runner_id": profile.runner_id,
            },
            "expected": "denied",
        },
        {
            "method": "POST",
            "path": "/rest/v1/rpc/heartbeat_automation_job",
            "body": {
                "target_job_id": profile.job_id,
                "target_runner_id": profile.runner_id,
            },
            "expected": "denied",
        },
        {
            "method": "POST",
            "path": "/rest/v1/rpc/finish_automation_job_run",
            "body": {
                "target_run_id": profile.run_id,
                "target_runner_id": profile.runner_id,
                "target_status": "succeeded",
                "target_records_read": 0,
                "target_error_code": None,
                "target_duration_ms": 0,
            },
            "expected": "denied",
        },
    ]


def role_probe_requests(
    role: str, scope: TargetProfile = LEGACY_PROFILE
) -> list[dict[str, object]]:
    scope = require_target_profile(scope)
    if role not in scope.roles:
        raise OperatorBlocked("ROLE_OUT_OF_SCOPE")
    workspace = {
        "method": "GET",
        "path": _workspace_path(scope),
        "body": None,
        "expected": "empty_workspace"
        if role in {"anonymous", "nonmember"}
        else "visible_workspace",
    }
    requests = [workspace]
    if role != "anonymous":
        requests.append(
            {
                "method": "POST",
                "path": _job_insert_path(),
                "body": _job_insert(scope),
                "expected": "job_created" if role == "owner" else "denied",
            }
        )
    if role in {"reviewer", "owner"}:
        requests.extend(_rpc_denials(scope))
    elif role == "anonymous":
        requests.append(_rpc_denials(scope)[0])
    if role == "owner":
        requests.append(
            {
                "method": "GET",
                "path": _job_get_path(scope),
                "body": None,
                "expected": "job_exists",
            }
        )
    return requests


def _safe_code(response: HttpResponse) -> str | None:
    if (
        not isinstance(response, HttpResponse)
        or len(response.body) > MAX_RESPONSE_BYTES
    ):
        return None
    try:
        value = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    code = (
        value.get("code", value.get("error_code")) if isinstance(value, dict) else None
    )
    if not isinstance(code, str) or len(code) > 64:
        return None
    if code not in _DENIAL_CODES and re.fullmatch(r"PGRST[0-9]{3}", code) is None:
        return None
    return code


def permission_denied(response: HttpResponse) -> bool:
    return (
        isinstance(response, HttpResponse)
        and response.status in {401, 403}
        and response.status != 404
        and _safe_code(response) in _DENIAL_CODES
    )


def edge_auth_gate_denied(response: HttpResponse) -> bool:
    return (
        isinstance(response, HttpResponse)
        and response.status == 401
        and _safe_code(response) in _AUTH_ERROR_CODES
    )


def _canonical_body(body: object) -> bytes | None:
    if body is None:
        return None
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _allowed_request(
    kind: str,
    role: str | None,
    method: str,
    path: str,
    body: object,
    scope: TargetProfile = LEGACY_PROFILE,
) -> bool:
    scope = require_target_profile(scope)
    if kind == "role":
        candidates = (
            role_probe_requests(role, scope)
            if role in scope.roles
            else [
                request
                for candidate_role in scope.roles
                for request in role_probe_requests(candidate_role, scope)
            ]
        )
        return any(
            request["method"] == method
            and request["path"] == path
            and (
                request["body"] == body
                or request["body"] == _job_insert(scope)
                and isinstance(body, dict)
                and _valid_uuid(body.get("requested_by"))
                and {**body, "requested_by": _CALLER} == _job_insert(scope)
            )
            for request in candidates
        )
    if kind in {"edge_negative", "edge_positive"}:
        return method == "POST" and path == EDGE_PATH and body == _edge_body(scope)
    return False


class OperatorLedger:
    """Append-only safe receipt; it never stores auth headers or raw bodies."""

    def __setattr__(self, name, value) -> None:
        if name == "_scope" and hasattr(self, "_scope"):
            raise AttributeError("operator profile is latched")
        object.__setattr__(self, name, value)

    def __init__(self, file: Path, *, scope: TargetProfile = LEGACY_PROFILE):
        scope = require_target_profile(scope)
        self._scope = scope
        self.file = Path(file)
        self.data: dict[str, object] = {
            "status": "OPERATOR_STARTED",
            "counts": {
                "role_total": 0,
                "role_by_name": dict.fromkeys(scope.roles, 0),
                "edge_negative": 0,
                "edge_positive": 0,
                "total": 0,
            },
            "role_results": [],
            "negative_edge_results": [],
            "intents": [],
            "stop_forward": False,
            "owner_job_verified": False,
            "edge_child_requests": "INFERRED_FROM_REVIEWED_SHARED_SOURCE",
        }
        if scope is FRESH_R13_PROFILE:
            self.data.update(
                scope_profile=scope.name,
                scope_digest=profile_scope_digest(scope),
            )
        self.file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.file.open("x", encoding="utf-8") as stream:
                json.dump(self.data, stream, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise OperatorBlocked("OPERATOR_ALREADY_ATTEMPTED") from error

    @property
    def scope(self) -> TargetProfile:
        return self._scope

    def _check_scope_binding(self) -> None:
        if self.scope is FRESH_R13_PROFILE:
            if self.data.get("scope_profile") != self.scope.name or self.data.get(
                "scope_digest"
            ) != profile_scope_digest(self.scope):
                raise OperatorBlocked("OPERATOR_PROFILE_MISMATCH")
        elif any(key in self.data for key in ("scope_profile", "scope_digest")):
            raise OperatorBlocked("OPERATOR_PROFILE_MISMATCH")

    def persist(self) -> None:
        self._check_scope_binding()
        with self.file.open("w", encoding="utf-8") as stream:
            json.dump(self.data, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())

    def reserve(
        self, kind: str, role: str | None, method: str, path: str, body: object
    ) -> dict[str, object]:
        self._check_scope_binding()
        counts = self.data["counts"]
        assert isinstance(counts, dict)
        by_role = counts["role_by_name"]
        assert isinstance(by_role, dict)
        if self.data["stop_forward"] or not _allowed_request(
            kind, role, method, path, body, self.scope
        ):
            raise OperatorBlocked("OPERATOR_SCOPE_BLOCKED")
        if counts["total"] >= self.scope.total_send_cap:
            raise OperatorBlocked("OPERATOR_TOTAL_BUDGET_EXCEEDED")
        if kind == "role":
            if (
                role not in self.scope.roles
                or counts["role_total"] >= self.scope.role_total_cap
            ):
                raise OperatorBlocked("OPERATOR_ROLE_BUDGET_EXCEEDED")
            if by_role[role] >= self.scope.role_caps[role]:
                raise OperatorBlocked("OPERATOR_ROLE_BUDGET_EXCEEDED")
            counts["role_total"] += 1
            by_role[role] += 1
        elif kind == "edge_negative":
            if counts["edge_negative"] >= self.scope.edge_negative_cap:
                raise OperatorBlocked("OPERATOR_EDGE_BUDGET_EXCEEDED")
            counts["edge_negative"] += 1
        else:
            if counts["edge_positive"] >= self.scope.edge_positive_cap:
                raise OperatorBlocked("OPERATOR_EDGE_BUDGET_EXCEEDED")
            counts["edge_positive"] += 1
        counts["total"] += 1
        encoded = _canonical_body(body)
        intent = {
            "ordinal": counts["total"],
            "kind": kind,
            "role": role,
            "method": method,
            "path": path,
            "body_sha256": hashlib.sha256(encoded).hexdigest()
            if encoded is not None
            else None,
            "outcome": "UNKNOWN",
        }
        intents = self.data["intents"]
        assert isinstance(intents, list)
        intents.append(intent)
        self.persist()  # The single-send allowance is consumed before network use.
        return intent

    def finish(
        self, intent: dict[str, object], response: HttpResponse | None
    ) -> str | None:
        self._check_scope_binding()
        if response is None:
            intent["outcome"] = "UNKNOWN"
            self.data["stop_forward"] = True
            self.persist()
            return None
        intent["outcome"] = f"HTTP_{response.status}"
        code = _safe_code(response)
        if code is not None:
            intent["safe_code"] = code
        self.persist()
        return code

    def stop(self, code: str) -> None:
        self._check_scope_binding()
        self.data["stop_forward"] = True
        self.data["status"] = code
        self.persist()


def _headers(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    allowed = {"Accept", "Authorization", "apikey", "Content-Type", "Prefer"}
    return {
        key: item
        for key, item in value.items()
        if key in allowed and isinstance(item, str)
    }


def _send_once(
    sender,
    method: str,
    path: str,
    headers: object,
    body: object,
    scope: TargetProfile = LEGACY_PROFILE,
):
    scope = require_target_profile(scope)
    body_bytes = _canonical_body(body)
    request_headers = _headers(headers)
    if body_bytes is not None:
        request_headers.setdefault("Content-Type", "application/json")
    try:
        url = f"{BASE_URL}{path}"
        if sender is http_request_once:
            response = sender(method, url, request_headers, body_bytes, scope=scope)
        else:
            response = sender(method, url, request_headers, body_bytes)
    except Exception:
        return None
    if (
        not isinstance(response, HttpResponse)
        or len(response.body) > MAX_RESPONSE_BYTES
    ):
        return None
    return response


def _object(response: HttpResponse):
    if len(response.body) > MAX_RESPONSE_BYTES:
        return None
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _exact_workspace(
    response: HttpResponse, visible: bool, scope: TargetProfile = LEGACY_PROFILE
) -> bool:
    scope = require_target_profile(scope)
    value = _object(response)
    if response.status != 200 or not isinstance(value, list):
        return False
    if not visible:
        return value == []
    return len(value) == 1 and value[0] == {
        "id": scope.workspace_id,
        "name": scope.workspace_name,
    }


def _exact_job(
    row: object, caller_user_id: str, scope: TargetProfile = LEGACY_PROFILE
) -> bool:
    scope = require_target_profile(scope)
    return (
        isinstance(row, dict)
        and row.get("id") == scope.job_id
        and row.get("workspace_id") == scope.workspace_id
        and row.get("type") == scope.job_type
        and row.get("status") == "queued"
        and row.get("idempotency_key") == scope.idempotency_key
        and row.get("requested_by") == caller_user_id
        and row.get("payload_json") == scope.payload
        and type(row.get("max_attempts")) is int
        and row.get("max_attempts") == scope.max_attempts
        and type(row.get("attempt_count")) is int
        and row.get("attempt_count") == 0
        and row.get("runner_id") is None
        and row.get("lease_expires_at") is None
        and row.get("heartbeat_at") is None
    )


def run_role_probes(
    role: str,
    sender,
    ledger: OperatorLedger,
    *,
    auth_headers: object,
    caller_user_id: str | None = None,
    scope: TargetProfile = LEGACY_PROFILE,
) -> dict[str, object]:
    scope = require_target_profile(scope)
    if ledger.scope is not scope:
        raise OperatorBlocked("OPERATOR_PROFILE_MISMATCH")
    if role not in scope.roles:
        return {"status": "BLOCKED", "error_code": "ROLE_OUT_OF_SCOPE"}
    if role != "anonymous" and (
        not _valid_uuid(caller_user_id) or not _headers(auth_headers)
    ):
        return {"status": "WAITING_AUTH_CAPABILITY", "role": role}
    private_headers = _headers(auth_headers)
    if role != "anonymous" and (
        not private_headers.get("Authorization", "").startswith("Bearer ")
        or not private_headers.get("apikey")
    ):
        return {"status": "WAITING_AUTH_CAPABILITY", "role": role}
    requests = role_probe_requests(role, scope)
    for descriptor in requests:
        body = _copy(descriptor["body"]) if descriptor["body"] is not None else None
        if isinstance(body, dict) and body.get("requested_by") == _CALLER:
            body["requested_by"] = caller_user_id
        intent = ledger.reserve(
            "role", role, descriptor["method"], descriptor["path"], body
        )
        response = _send_once(
            sender, descriptor["method"], descriptor["path"], auth_headers, body, scope
        )
        code = ledger.finish(intent, response)
        if response is None:
            ledger.stop("ROLE_REQUEST_UNKNOWN")
            return {"status": "UNKNOWN", "role": role}
        expected = descriptor["expected"]
        if expected == "empty_workspace" or expected == "visible_workspace":
            passed = _exact_workspace(response, expected == "visible_workspace", scope)
        elif expected == "denied":
            if 200 <= response.status < 300:
                ledger.stop("UNEXPECTED_ROLE_ACCEPTANCE")
                return {"status": "BLOCKED_UNEXPECTED_ACCEPTANCE", "role": role}
            passed = permission_denied(response)
        elif expected == "job_created":
            value = _object(response)
            passed = (
                response.status == 201
                and isinstance(value, list)
                and len(value) == 1
                and _exact_job(value[0], caller_user_id or "", scope)
            )
            ledger.data["owner_job_verified"] = passed
        else:
            value = _object(response)
            passed = (
                response.status == 200
                and isinstance(value, list)
                and len(value) == 1
                and _exact_job(value[0], caller_user_id or "", scope)
            )
            ledger.data["owner_job_verified"] = passed
        if not passed:
            ledger.stop("ROLE_PROBE_INCOMPLETE")
            return {"status": "INCOMPLETE", "role": role, "safe_code": code}
        results = ledger.data["role_results"]
        assert isinstance(results, list)
        results.append(
            {"role": role, "probe": expected, "status": "PASS", "safe_code": code}
        )
        ledger.persist()
    counts = ledger.data["counts"]
    assert isinstance(counts, dict) and isinstance(counts["role_by_name"], dict)
    results = ledger.data["role_results"]
    if (
        counts["role_total"] == scope.role_total_cap
        and len(results) == scope.role_total_cap
    ):
        ledger.data["role_matrix_complete"] = True
    ledger.persist()
    return {"status": "PASS", "role": role, "probes": len(requests)}


def probe_edge_negative(
    role: str,
    principal: object,
    sender,
    ledger: OperatorLedger,
    *,
    scope: TargetProfile = LEGACY_PROFILE,
):
    scope = require_target_profile(scope)
    if ledger.scope is not scope:
        raise OperatorBlocked("OPERATOR_PROFILE_MISMATCH")
    if role not in {"anonymous", "nonmember", "reviewer"}:
        return {"status": "BLOCKED", "error_code": "EDGE_ROLE_OUT_OF_SCOPE"}
    private_headers = _headers(principal)
    if role != "anonymous" and (
        not private_headers.get("Authorization", "").startswith("Bearer ")
        or not private_headers.get("apikey")
    ):
        return {"status": "WAITING_AUTH_CAPABILITY", "role": role}
    intent = ledger.reserve("edge_negative", role, "POST", EDGE_PATH, _edge_body(scope))
    response = _send_once(
        sender, "POST", EDGE_PATH, principal, _edge_body(scope), scope
    )
    code = ledger.finish(intent, response)
    if response is None:
        ledger.stop("EDGE_REQUEST_UNKNOWN")
        outcome = {"role": role, "status": "UNKNOWN", "safe_code": None}
    elif 200 <= response.status < 300:
        ledger.stop("UNEXPECTED_NEGATIVE_EDGE_ACCEPTANCE")
        outcome = {
            "role": role,
            "status": "BLOCKED_UNEXPECTED_ACCEPTANCE",
            "safe_code": code,
        }
    elif role == "anonymous" and edge_auth_gate_denied(response):
        outcome = {"role": role, "status": "AUTH_GATE_ONLY", "safe_code": code}
    elif (
        role in {"nonmember", "reviewer"}
        and response.status == 403
        and code == "OWNER_REQUIRED"
    ):
        outcome = {"role": role, "status": "DENIED_OWNER_REQUIRED", "safe_code": code}
    else:
        ledger.stop("EDGE_DENIAL_UNPROVEN")
        outcome = {"role": role, "status": "INCOMPLETE", "safe_code": code}
    results = ledger.data["negative_edge_results"]
    assert isinstance(results, list)
    results.append(outcome)
    ledger.persist()
    return outcome


def _positive_ready(
    ledger: OperatorLedger,
    marker_sha: str,
    approved_sha: str,
    final_scope: bool,
    scope: TargetProfile = LEGACY_PROFILE,
) -> bool:
    scope = require_target_profile(scope)
    counts = ledger.data["counts"]
    results = ledger.data["negative_edge_results"]
    role_results = ledger.data["role_results"]
    return (
        ledger.data["stop_forward"] is False
        and ledger.scope is scope
        and isinstance(counts, dict)
        and counts.get("role_total") == scope.role_total_cap
        and counts.get("edge_negative") == scope.edge_negative_cap
        and counts.get("edge_positive") == 0
        and ledger.data.get("role_matrix_complete") is True
        and ledger.data.get("owner_job_verified") is True
        and isinstance(role_results, list)
        and len(role_results) == scope.role_total_cap
        and isinstance(results, list)
        and len(results) == scope.edge_negative_cap
        and {item.get("role") for item in results if isinstance(item, dict)}
        == {"anonymous", "nonmember", "reviewer"}
        and all(
            item.get("status") in {"AUTH_GATE_ONLY", "DENIED_OWNER_REQUIRED"}
            for item in results
            if isinstance(item, dict)
        )
        and _valid_sha(marker_sha)
        and marker_sha == approved_sha
        and _valid_sha(approved_sha)
        and final_scope is True
    )


def dispatch_existing_job(
    principal: object,
    sender,
    ledger: OperatorLedger,
    *,
    marker_sha: str,
    approved_sha: str,
    final_scope: bool,
    scope: TargetProfile = LEGACY_PROFILE,
):
    scope = require_target_profile(scope)
    if not _positive_ready(ledger, marker_sha, approved_sha, final_scope, scope):
        return {"status": "BLOCKED", "error_code": "POSITIVE_DISPATCH_GATES_INCOMPLETE"}
    private_headers = _headers(principal)
    if not private_headers.get("Authorization", "").startswith(
        "Bearer "
    ) or not private_headers.get("apikey"):
        return {"status": "WAITING_AUTH_CAPABILITY"}
    edge_body = _edge_body(scope)
    intent = ledger.reserve("edge_positive", "owner", "POST", EDGE_PATH, edge_body)
    response = _send_once(sender, "POST", EDGE_PATH, principal, edge_body, scope)
    code = ledger.finish(intent, response)
    if response is None:
        ledger.stop("POSITIVE_DISPATCH_UNKNOWN")
        return {"status": "UNKNOWN", "safe_code": None}
    value = _object(response)
    if (
        response.status == 202
        and isinstance(value, dict)
        and value.get("job_id") == scope.job_id
        and value.get("status") == "dispatched"
        and value.get("created") is False
    ):
        ledger.data["status"] = "DISPATCH_ACCEPTED_EXISTING_JOB"
        ledger.data["positive_result"] = {
            "http_status": response.status,
            "job_id": scope.job_id,
            "job_status": "dispatched",
            "created": False,
        }
        ledger.persist()
        return {"status": "PASS", **ledger.data["positive_result"]}
    ledger.stop("POSITIVE_DISPATCH_UNCONFIRMED")
    return {"status": "INCOMPLETE", "safe_code": code}


def http_request_once(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    scope: TargetProfile = LEGACY_PROFILE,
):
    scope = require_target_profile(scope)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != f"{PROJECT_REF}.supabase.co":
        raise OperatorBlocked("OPERATOR_ENDPOINT_BLOCKED")
    try:
        parsed_body = json.loads(body.decode("utf-8")) if body is not None else None
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OperatorBlocked("OPERATOR_REQUEST_BODY_BLOCKED") from error
    if not (
        any(
            _allowed_request(
                "role",
                role,
                method,
                parsed.path + (f"?{parsed.query}" if parsed.query else ""),
                parsed_body,
                scope,
            )
            for role in scope.roles
        )
        or _allowed_request(
            "edge_negative", None, method, parsed.path, parsed_body, scope
        )
    ):
        raise OperatorBlocked("OPERATOR_REQUEST_PATH_BLOCKED")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=15) as response:
            return HttpResponse(response.status, response.read(MAX_RESPONSE_BYTES + 1))
    except urllib.error.HTTPError as error:
        return HttpResponse(error.code, error.read(MAX_RESPONSE_BYTES + 1))


SQL_TEMPLATES = {
    "setup": f"""-- Bind :auth_user_id only inside the trusted operator session.
do $$ begin
  if exists (select 1 from public.workspaces where id = '{WORKSPACE_ID}'::uuid
             or name = '{WORKSPACE_NAME}') then
    raise exception 'PILOT_WORKSPACE_COLLISION';
  end if;
  insert into public.workspaces (id, name, timezone)
  values ('{WORKSPACE_ID}'::uuid, '{WORKSPACE_NAME}', 'Asia/Ho_Chi_Minh');
end $$;""",
    "reviewer": f"""-- :auth_user_id is supplied privately by the trusted operator.
do $$ begin
  if not exists (select 1 from public.workspaces
                 where id = '{WORKSPACE_ID}'::uuid and name = '{WORKSPACE_NAME}') then
    raise exception 'PILOT_WORKSPACE_MISMATCH';
  end if;
  if exists (select 1 from public.workspace_members
             where workspace_id = '{WORKSPACE_ID}'::uuid) then
    raise exception 'PILOT_MEMBER_COLLISION';
  end if;
  insert into public.workspace_members (workspace_id, user_id, role)
  values ('{WORKSPACE_ID}'::uuid, :auth_user_id, 'reviewer');
end $$;""",
    "owner": f"""-- :auth_user_id is supplied privately by the trusted operator.
do $$ begin
  if not exists (select 1 from public.workspaces
                 where id = '{WORKSPACE_ID}'::uuid and name = '{WORKSPACE_NAME}') then
    raise exception 'PILOT_WORKSPACE_MISMATCH';
  end if;
  if (select count(*) from public.workspace_members
      where workspace_id = '{WORKSPACE_ID}'::uuid and user_id = :auth_user_id
        and role = 'reviewer') <> 1
     or (select count(*) from public.workspace_members
         where workspace_id = '{WORKSPACE_ID}'::uuid) <> 1 then
    raise exception 'PILOT_MEMBER_MISMATCH';
  end if;
  update public.workspace_members set role = 'owner'
  where workspace_id = '{WORKSPACE_ID}'::uuid and user_id = :auth_user_id
    and role = 'reviewer';
end $$;""",
    "cleanup": f"""-- Removes only the exact synthetic workspace after its job is terminal.
do $$
declare
  target_workspace public.workspaces;
  target_job public.automation_jobs;
begin
  select * into target_workspace
  from public.workspaces
  where id = '{WORKSPACE_ID}'::uuid
  for update;
  if target_workspace.id is not null
     and target_workspace.name is distinct from '{WORKSPACE_NAME}' then
    raise exception 'PILOT_WORKSPACE_COLLISION';
  end if;

  perform 1 from public.workspace_members
  where workspace_id = '{WORKSPACE_ID}'::uuid
  for update;
  if exists (select 1 from public.workspace_members
             where workspace_id = '{WORKSPACE_ID}'::uuid and user_id <> :auth_user_id) then
    raise exception 'PILOT_MEMBER_COLLISION';
  end if;
  if exists (select 1 from public.workspaces
             where name = '{WORKSPACE_NAME}' and id <> '{WORKSPACE_ID}'::uuid) then
    raise exception 'PILOT_WORKSPACE_COLLISION';
  end if;
  if exists (select 1 from public.automation_jobs
             where workspace_id = '{WORKSPACE_ID}'::uuid and id <> '{JOB_ID}'::uuid) then
    raise exception 'PILOT_JOB_COLLISION';
  end if;

  select * into target_job
  from public.automation_jobs
  where id = '{JOB_ID}'::uuid
  for update;
  if target_job.id is not null then
    if target_job.workspace_id is distinct from '{WORKSPACE_ID}'::uuid
       or target_job.type is distinct from '{JOB_TYPE}'
       or target_job.idempotency_key is distinct from '{IDEMPOTENCY_KEY}'
       or target_job.payload_json is distinct from '{json.dumps(PAYLOAD, separators=(",", ":"))}'::jsonb
       or target_job.requested_by is distinct from :auth_user_id
       or target_job.max_attempts is distinct from 1 then
      raise exception 'PILOT_JOB_COLLISION';
    end if;
    if target_job.status not in ('succeeded', 'cancelled')
       and not (
         target_job.status in ('failed', 'partial')
         and target_job.attempt_count >= target_job.max_attempts
       ) then
      raise exception 'PILOT_JOB_NOT_TERMINAL';
    end if;
    if exists (select 1 from public.automation_runs run
               where run.job_id = target_job.id
                 and (run.status = 'running' or run.finished_at is null)) then
      raise exception 'PILOT_RUN_STILL_ACTIVE';
    end if;
  end if;
  delete from public.automation_jobs
  where id = '{JOB_ID}'::uuid and workspace_id = '{WORKSPACE_ID}'::uuid
    and idempotency_key = '{IDEMPOTENCY_KEY}'
    and payload_json = '{json.dumps(PAYLOAD, separators=(",", ":"))}'::jsonb;
  delete from public.workspaces
  where id = '{WORKSPACE_ID}'::uuid and name = '{WORKSPACE_NAME}';
end $$;""",
}


def sql_templates(scope: TargetProfile = LEGACY_PROFILE) -> dict[str, str]:
    scope = require_target_profile(scope)
    if scope is LEGACY_PROFILE:
        return SQL_TEMPLATES

    old_payload = json.dumps(PAYLOAD, separators=(",", ":"))
    new_payload = json.dumps(scope.payload, separators=(",", ":"))
    replacements = (
        (old_payload, new_payload),
        (WORKSPACE_ID, scope.workspace_id),
        (WORKSPACE_NAME, scope.workspace_name),
        (JOB_ID, scope.job_id),
        (JOB_TYPE, scope.job_type),
        (IDEMPOTENCY_KEY, scope.idempotency_key),
    )
    return {
        name: _replace_sql_values(template, replacements)
        for name, template in SQL_TEMPLATES.items()
    }


def _replace_sql_values(
    template: str, replacements: tuple[tuple[str, str], ...]
) -> str:
    for original, replacement in replacements:
        template = template.replace(original, replacement)
    return template


def live_capability_status(*, official_session, approved_head, final_packet) -> str:
    if official_session is None:
        return "WAITING_AUTH_CAPABILITY"
    verified = getattr(official_session, "verified_official_app_session", False) is True
    if not verified:
        return "WAITING_AUTH_CAPABILITY"
    if (
        not isinstance(approved_head, str)
        or re.fullmatch(r"[a-f0-9]{40}", approved_head) is None
        or not isinstance(final_packet, Mapping)
        or final_packet.get("status") != "EXACT_SCOPE_APPROVED"
        or final_packet.get("head") != approved_head
    ):
        return "WAITING_FINAL_SCOPE"
    return "CAPABILITY_PRESENT_NOT_EXECUTED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps({"status": "WAITING_AUTH_CAPABILITY"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
