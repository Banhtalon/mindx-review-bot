"""One private app session, ordered fixed-scope commands, existing operator guards."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

from app_session_receiver import MAX_INPUT_BYTES, process_input
from api_chain_continuation import GIT, check_source_head
from api_chain_operator import (
    FRESH_R13_PROFILE,
    LEGACY_PROFILE,
    OperatorBlocked,
    OperatorLedger,
    TargetProfile,
    dispatch_existing_job,
    http_request_once,
    live_capability_status,
    profile_budget_caps,
    profile_scope_digest,
    require_target_profile,
    target_scope_manifest,
    probe_edge_negative,
    run_role_probes,
    _valid_sha,
)
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / ".workflow-local" / "api-chain-session"
WORKFLOW_HEAD = "1855c37a6f1347cd70d14f9b9eb6eec52596823a"
PHASES = ("nonmember", "reviewer", "owner", "dispatch")
R13_APPROVAL_SCHEMA = "mindx.api-chain-r13.approval.v1"
LEGACY_SOURCE_PATHS = frozenset(
    {
        "scripts/app_session_host.mjs",
        "scripts/lib/app_session.mjs",
        "scripts/app_session_receiver.py",
        "scripts/api_chain_operator.py",
        "scripts/api_chain_session.py",
        "scripts/api_chain_session_host.mjs",
        "scripts/api_chain_continuation.py",
    }
)
R13_SOURCE_PATHS = LEGACY_SOURCE_PATHS | frozenset(
    {
        "scripts/api_chain_synthetic_pilot.py",
        ".github/workflows/spike0-dispatch-probe.yml",
    }
)


class SessionApproval(NamedTuple):
    digest: str
    profile: TargetProfile
    workflow_head: str
    actor_sha256: str | None


def _check_clean_head(root: Path, approved_head: str) -> None:
    check_source_head(root, approved_head)
    clean = subprocess.run(
        [GIT, "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        timeout=5,
        check=False,
    )
    if clean.returncode != 0 or clean.stdout.strip():
        raise ValueError("EXACT_HEAD_CHANGED")


def _exact_budget_caps(value: object) -> bool:
    expected = profile_budget_caps(FRESH_R13_PROFILE)
    if not isinstance(value, dict) or set(value) != set(expected):
        return False
    if any(
        type(value.get(key)) is not int
        for key in ("role_total", "edge_negative", "edge_positive", "total")
    ):
        return False
    role_caps = value.get("role_by_name")
    expected_roles = expected["role_by_name"]
    return (
        isinstance(role_caps, dict)
        and set(role_caps) == set(expected_roles)
        and all(type(role_caps.get(role)) is int for role in expected_roles)
        and value == expected
    )


def _load_scope(folder=FOLDER, root=ROOT) -> SessionApproval:
    raw = (folder / "approval.json").read_bytes()
    if len(raw) > 8192:
        raise ValueError("SCOPE_BLOCKED")
    scope = json.loads(raw)
    if not isinstance(scope, dict):
        raise ValueError("SCOPE_BLOCKED")

    r13 = scope.get("schema_version") == R13_APPROVAL_SCHEMA
    if r13:
        required = {
            "schema_version",
            "profile",
            "status",
            "head",
            "workflow_head",
            "contract_sha256",
            "scope",
            "scope_digest",
            "actor_sha256",
            "budget_caps",
            "source_sha256",
        }
        if (
            set(scope) != required
            or scope.get("profile") != FRESH_R13_PROFILE.name
            or not _valid_sha(scope.get("head"))
            or scope.get("workflow_head") != scope.get("head")
            or scope.get("scope") != target_scope_manifest(FRESH_R13_PROFILE)
            or scope.get("scope_digest") != profile_scope_digest(FRESH_R13_PROFILE)
            or not isinstance(scope.get("actor_sha256"), str)
            or re.fullmatch(r"[a-f0-9]{64}", scope["actor_sha256"]) is None
            or not _exact_budget_caps(scope.get("budget_caps"))
        ):
            raise ValueError("R13_SCOPE_BLOCKED")
        profile = FRESH_R13_PROFILE
        workflow_head = scope["head"]
        actor_sha256 = scope["actor_sha256"]
        expected_sources = R13_SOURCE_PATHS
    else:
        if scope.get("schema_version") is not None or any(
            key in scope
            for key in (
                "profile",
                "scope",
                "scope_digest",
                "actor_sha256",
                "budget_caps",
            )
        ):
            raise ValueError("SCOPE_BLOCKED")
        profile = LEGACY_PROFILE
        workflow_head = WORKFLOW_HEAD
        actor_sha256 = None
        expected_sources = LEGACY_SOURCE_PATHS

    if (
        scope.get("workflow_head") != workflow_head
        or live_capability_status(
            official_session=SimpleNamespace(verified_official_app_session=True),
            approved_head=scope.get("head"),
            final_packet=scope,
        )
        != "CAPABILITY_PRESENT_NOT_EXECUTED"
        or scope.get("contract_sha256")
        != hashlib.sha256((folder / "TASK.md").read_bytes()).hexdigest()
    ):
        raise ValueError("SCOPE_BLOCKED")
    hashes = scope.get("source_sha256")
    if not isinstance(hashes, dict) or set(hashes) != expected_sources:
        raise ValueError("SOURCE_BLOCKED")
    for name, digest in hashes.items():
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"[a-f0-9]{64}", digest) is None
            or hashlib.sha256((root / name).read_bytes()).hexdigest() != digest
        ):
            raise ValueError("SOURCE_BLOCKED")
    if profile is FRESH_R13_PROFILE:
        _check_clean_head(root, scope.get("head"))
    else:
        check_source_head(root, scope.get("head"))
    return SessionApproval(
        hashlib.sha256(raw).hexdigest(),
        profile,
        workflow_head,
        actor_sha256,
    )


def check_scope(folder=FOLDER, root=ROOT):
    return _load_scope(folder, root).digest


def _validate_session_context(
    context: object, approval: SessionApproval, *, now: float | None = None
) -> None:
    if not isinstance(context, dict):
        raise ValueError("SESSION_BLOCKED")
    expires_at = context.get("expires_at")
    if type(expires_at) is not int:
        raise ValueError("SESSION_EXPIRED")
    current = time.time() if now is None else now
    if expires_at < current + 360:
        raise ValueError("SESSION_TOO_SHORT")
    if approval.profile is FRESH_R13_PROFILE:
        user_id = context.get("user_uuid")
        if (
            not isinstance(user_id, str)
            or hashlib.sha256(user_id.encode()).hexdigest() != approval.actor_sha256
        ):
            raise ValueError("ACTOR_BLOCKED")


def command(value, expected, previous, *, workflow_head=WORKFLOW_HEAD):
    if not isinstance(value, dict):
        raise ValueError("COMMAND_BLOCKED")
    if value == previous:
        return False
    fields = {"phase", "marker_sha"} if expected == "dispatch" else {"phase"}
    if set(value) != fields or value.get("phase") != expected:
        raise ValueError("COMMAND_BLOCKED")
    if expected == "dispatch":
        if not _valid_sha(workflow_head) or value["marker_sha"] != workflow_head:
            raise ValueError("MARKER_BLOCKED")
    return True


def execute_phase(
    phase,
    context,
    ledger,
    sender=http_request_once,
    *,
    validate_scope=check_scope,
    scope_digest=None,
    scope=LEGACY_PROFILE,
    workflow_head=WORKFLOW_HEAD,
):
    scope = require_target_profile(scope)
    if ledger.scope is not scope:
        raise OperatorBlocked("OPERATOR_PROFILE_MISMATCH")
    if scope_digest is None:
        scope_digest = validate_scope()

    def guarded_sender(method, url, headers, body):
        if validate_scope() != scope_digest:
            raise ValueError("SCOPE_CHANGED")
        if sender is http_request_once:
            return sender(method, url, headers, body, scope=scope)
        return sender(method, url, headers, body)

    headers = {
        "apikey": context["public_key"],
        "Authorization": "Bearer " + context["access_token"],
        "Prefer": "return=representation",
    }
    anon = {"apikey": context["public_key"]}
    if phase == "dispatch":
        if scope is LEGACY_PROFILE:
            result = dispatch_existing_job(
                headers,
                guarded_sender,
                ledger,
                marker_sha=WORKFLOW_HEAD,
                approved_sha=WORKFLOW_HEAD,
                final_scope=True,
            )
        else:
            result = dispatch_existing_job(
                headers,
                guarded_sender,
                ledger,
                marker_sha=workflow_head,
                approved_sha=workflow_head,
                final_scope=True,
                scope=scope,
            )
        if result["status"] != "PASS":
            raise ValueError("DISPATCH_INCOMPLETE")
    else:
        for role in ("anonymous", "nonmember") if phase == "nonmember" else (phase,):
            principal = anon if role == "anonymous" else headers
            caller_user_id = None if role == "anonymous" else context["user_uuid"]
            if scope is LEGACY_PROFILE:
                result = run_role_probes(
                    role,
                    guarded_sender,
                    ledger,
                    auth_headers=principal,
                    caller_user_id=caller_user_id,
                )
            else:
                result = run_role_probes(
                    role,
                    guarded_sender,
                    ledger,
                    auth_headers=principal,
                    caller_user_id=caller_user_id,
                    scope=scope,
                )
            if result["status"] != "PASS":
                raise ValueError("ROLE_INCOMPLETE")
            if role != "owner":
                if scope is LEGACY_PROFILE:
                    result = probe_edge_negative(
                        role, principal, guarded_sender, ledger
                    )
                else:
                    result = probe_edge_negative(
                        role, principal, guarded_sender, ledger, scope=scope
                    )
                if result["status"] not in {"AUTH_GATE_ONLY", "DENIED_OWNER_REQUIRED"}:
                    raise ValueError("EDGE_INCOMPLETE")


def main():
    ledger = None
    try:
        if len(sys.argv) != 1:
            raise ValueError("ARGS_BLOCKED")
        approval = _load_scope()
        scope_digest = approval.digest
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if process_input(raw) != {"status": "WAITING_FINAL_SCOPE"}:
            raise ValueError("SESSION_BLOCKED")
        context = json.loads(raw)
        raw = b""
        _validate_session_context(context, approval)
        if approval.profile is LEGACY_PROFILE:
            ledger = OperatorLedger(FOLDER / "operator-receipt.json")
        else:
            ledger = OperatorLedger(
                FOLDER / "operator-receipt.json", scope=approval.profile
            )
        ledger.data.update(
            session_actor_sha256=hashlib.sha256(
                context["user_uuid"].encode()
            ).hexdigest(),
            phase_status="READY_NO_SEND",
            phases=[],
        )
        ledger.persist()
        print("SESSION_READY", flush=True)
        deadline = time.monotonic() + 300
        previous = None
        for phase in PHASES:
            while True:
                if (
                    time.monotonic() >= deadline
                    or context["expires_at"] <= time.time() + 30
                ):
                    raise ValueError("SESSION_EXPIRED")
                if check_scope() != scope_digest:
                    raise ValueError("SCOPE_CHANGED")
                control = FOLDER / "control.json"
                if control.exists():
                    value = json.loads(control.read_bytes()[:1025])
                    if approval.profile is LEGACY_PROFILE:
                        accepted = command(value, phase, previous)
                    else:
                        accepted = command(
                            value,
                            phase,
                            previous,
                            workflow_head=approval.workflow_head,
                        )
                    if accepted:
                        break
                time.sleep(0.25)
            ledger.data["phase_status"] = phase + "_STARTED"
            ledger.persist()
            if approval.profile is LEGACY_PROFILE:
                execute_phase(phase, context, ledger, scope_digest=scope_digest)
            else:
                execute_phase(
                    phase,
                    context,
                    ledger,
                    scope_digest=scope_digest,
                    scope=approval.profile,
                    workflow_head=approval.workflow_head,
                )
            ledger.data["phases"].append(phase)
            ledger.data["phase_status"] = phase + "_PASS"
            ledger.persist()
            previous = value
        context.clear()
        return 0
    except Exception:
        if ledger is not None:
            ledger.data["phase_status"] = "STOPPED_RECONCILE_ONLY"
            ledger.stop("SESSION_OPERATOR_BLOCKED")
        print("SESSION_OPERATOR_BLOCKED", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
