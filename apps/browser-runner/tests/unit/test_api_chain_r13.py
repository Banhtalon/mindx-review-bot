"""R13 uses synthetic fixed identities and fake transports only."""

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps" / "browser-runner" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import api_chain_operator as operator  # noqa: E402, I001
import api_chain_session as session  # noqa: E402
import api_chain_synthetic_pilot as pilot  # noqa: E402
from mindx_runner.supabase_client import HttpResponse  # noqa: E402

PROFILE = operator.FRESH_R13_PROFILE
HEAD = "b" * 40
ACTOR = "20000000-0000-4000-8000-000000000001"
WORKER_RUN_ID = "90000000-0000-4000-8000-000000000001"


def fresh_environment(*, preflight=False):
    environment = {
        "GITHUB_REPOSITORY": "Banhtalon/mindx-review-bot",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "84",
        "GITHUB_SHA": HEAD,
        pilot.APPROVAL: HEAD,
        "JOB_ID": PROFILE.job_id,
        "JOB_TYPE": PROFILE.job_type,
    }
    if preflight:
        environment["GITHUB_TOKEN"] = "synthetic-read-only-token"
    else:
        environment["SUPABASE_SECRET_KEY"] = "synthetic-runner-key"
    return environment


def fresh_run(**changes):
    value = {
        "id": 84,
        "display_title": f"spike0 synthetic {PROFILE.job_id}",
        "name": f"spike0 synthetic {PROFILE.job_id}",
        "path": f".github/workflows/{pilot.WORKFLOW_FILE}",
        "head_sha": HEAD,
        "head_branch": "main",
        "event": "workflow_dispatch",
        "run_attempt": 1,
        "run_number": 18,
    }
    value.update(changes)
    return value


def history_bytes(*runs, total=None):
    return json.dumps(
        {
            "total_count": len(runs) if total is None else total,
            "workflow_runs": runs,
        }
    ).encode()


def test_profiles_are_fixed_and_sql_is_bound_to_the_selected_profile():
    assert operator.profile_for_job_id(PROFILE.job_id) is PROFILE
    assert operator.profile_for_job_id(operator.JOB_ID) is operator.LEGACY_PROFILE
    with pytest.raises(operator.OperatorBlocked, match="PROFILE_OUT_OF_SCOPE"):
        operator.profile_for_job_id("c8841b3c-5740-5b0a-aeaf-9dad5f5f17a6")
    with pytest.raises(AttributeError):
        PROFILE.job_id = operator.JOB_ID

    old_sql = operator.sql_templates()
    fresh_sql = operator.sql_templates(PROFILE)
    assert old_sql is operator.SQL_TEMPLATES
    assert set(fresh_sql) == {"setup", "reviewer", "owner", "cleanup"}
    assert all(PROFILE.workspace_id in sql for sql in fresh_sql.values())
    assert PROFILE.job_id in fresh_sql["cleanup"]
    assert all(operator.JOB_ID not in sql for sql in fresh_sql.values())
    assert all(operator.WORKSPACE_ID not in sql for sql in fresh_sql.values())
    with pytest.raises(operator.OperatorBlocked, match="PROFILE_OUT_OF_SCOPE"):
        operator.sql_templates(operator.TargetProfile(*PROFILE))


def test_fresh_operator_runs_exact_role_matrix_edge_denials_and_one_dispatch(tmp_path):
    ledger = operator.OperatorLedger(tmp_path / "fresh-operator.json", scope=PROFILE)
    sent = []
    current = {"role": None, "positive": False}
    caller_id = ACTOR

    def sender(method, url, headers, body):
        path = url.split("gnvzjvgfsxfjgldatbwt.supabase.co", 1)[-1]
        decoded = json.loads(body.decode()) if body else None
        sent.append((method, path, decoded))
        role = current["role"]
        if path == operator.EDGE_PATH:
            if current["positive"]:
                return HttpResponse(
                    202,
                    json.dumps(
                        {
                            "job_id": PROFILE.job_id,
                            "status": "dispatched",
                            "created": False,
                        }
                    ).encode(),
                )
            if role == "anonymous":
                return HttpResponse(401, b'{"error_code":"AUTH_REQUIRED"}')
            return HttpResponse(403, b'{"code":"OWNER_REQUIRED"}')
        if "/rpc/" in path:
            return HttpResponse(403, b'{"code":"42501"}')
        if path.startswith("/rest/v1/workspaces?"):
            rows = (
                []
                if role in {"anonymous", "nonmember"}
                else [{"id": PROFILE.workspace_id, "name": PROFILE.workspace_name}]
            )
            return HttpResponse(200, json.dumps(rows).encode())
        if path.startswith("/rest/v1/automation_jobs?") and method == "POST":
            if role != "owner":
                return HttpResponse(403, b'{"code":"42501"}')
            row = dict(decoded)
            row.update(attempt_count=0, runner_id=None, lease_expires_at=None, heartbeat_at=None)
            return HttpResponse(201, json.dumps([row]).encode())
        if path.startswith("/rest/v1/automation_jobs?") and method == "GET":
            row = operator._job_insert(PROFILE)
            row.update(
                requested_by=caller_id,
                attempt_count=0,
                runner_id=None,
                lease_expires_at=None,
                heartbeat_at=None,
            )
            return HttpResponse(200, json.dumps([row]).encode())
        raise AssertionError(f"unexpected synthetic route: {path}")

    for role in PROFILE.roles:
        current["role"] = role
        headers = (
            {"apikey": "synthetic-anon"}
            if role == "anonymous"
            else {"apikey": "synthetic-anon", "Authorization": f"Bearer synthetic-{role}"}
        )
        result = operator.run_role_probes(
            role,
            sender,
            ledger,
            auth_headers=headers,
            caller_user_id=None if role == "anonymous" else caller_id,
            scope=PROFILE,
        )
        assert result["status"] == "PASS"
        if role != "owner":
            edge = operator.probe_edge_negative(
                role,
                headers,
                sender,
                ledger,
                scope=PROFILE,
            )
            assert edge["status"] in {"AUTH_GATE_ONLY", "DENIED_OWNER_REQUIRED"}

    assert ledger.data["counts"] == {
        "role_total": 15,
        "role_by_name": {"anonymous": 2, "nonmember": 2, "reviewer": 5, "owner": 6},
        "edge_negative": 3,
        "edge_positive": 0,
        "total": 18,
    }
    current.update(role="owner", positive=True)
    result = operator.dispatch_existing_job(
        {"apikey": "synthetic-anon", "Authorization": "Bearer synthetic-owner"},
        sender,
        ledger,
        marker_sha=HEAD,
        approved_sha=HEAD,
        final_scope=True,
        scope=PROFILE,
    )
    assert result["status"] == "PASS"
    assert ledger.data["counts"]["total"] == 19
    assert ledger.data["counts"]["edge_positive"] == 1
    serialized_sent = json.dumps(sent)
    assert PROFILE.job_id in serialized_sent and PROFILE.workspace_id in serialized_sent
    assert operator.JOB_ID not in serialized_sent


def test_operator_rejects_mixed_response_and_scope_rebinding_before_send(tmp_path):
    row = operator._job_insert(PROFILE)
    assert not operator._exact_job({**row, "id": operator.JOB_ID}, ACTOR, PROFILE)

    ledger = operator.OperatorLedger(tmp_path / "scope.json", scope=PROFILE)
    sender = Mock(
        return_value=HttpResponse(
            202,
            json.dumps(
                {
                    "job_id": operator.JOB_ID,
                    "status": "dispatched",
                    "created": False,
                }
            ).encode(),
        )
    )
    ledger.data.update(
        role_matrix_complete=True,
        owner_job_verified=True,
        role_results=[
            {"role": role, "status": "PASS"}
            for role in PROFILE.roles
            for _ in range(PROFILE.role_caps[role])
        ],
        negative_edge_results=[
            {"role": "anonymous", "status": "AUTH_GATE_ONLY"},
            {"role": "nonmember", "status": "DENIED_OWNER_REQUIRED"},
            {"role": "reviewer", "status": "DENIED_OWNER_REQUIRED"},
        ],
    )
    ledger.data["counts"].update(
        role_total=15,
        role_by_name=PROFILE.role_caps,
        edge_negative=3,
        total=18,
    )
    result = operator.dispatch_existing_job(
        {"apikey": "synthetic-anon", "Authorization": "Bearer synthetic-owner"},
        sender,
        ledger,
        marker_sha=HEAD,
        approved_sha=HEAD,
        final_scope=True,
        scope=PROFILE,
    )
    assert result["status"] == "INCOMPLETE"
    assert sender.call_count == 1

    mutated = operator.OperatorLedger(tmp_path / "mutated.json", scope=PROFILE)
    mutated.data["scope_profile"] = "LEGACY"
    with pytest.raises(operator.OperatorBlocked, match="PROFILE_MISMATCH"):
        mutated.reserve(
            "edge_positive",
            "owner",
            "POST",
            operator.EDGE_PATH,
            operator._edge_body(PROFILE),
        )
    with pytest.raises(AttributeError):
        mutated.scope = operator.LEGACY_PROFILE


def _r13_approval_fixture(tmp_path):
    folder = tmp_path / "packet"
    root = tmp_path / "repo"
    folder.mkdir()
    root.mkdir()
    contract = b"synthetic R13 session contract"
    (folder / "TASK.md").write_bytes(contract)
    sources = {}
    for name in sorted(session.R13_SOURCE_PATHS):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"synthetic source: {name}".encode())
        sources[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    approval = {
        "schema_version": session.R13_APPROVAL_SCHEMA,
        "profile": PROFILE.name,
        "status": "EXACT_SCOPE_APPROVED",
        "head": HEAD,
        "workflow_head": HEAD,
        "contract_sha256": hashlib.sha256(contract).hexdigest(),
        "scope": operator.target_scope_manifest(PROFILE),
        "scope_digest": operator.profile_scope_digest(PROFILE),
        "actor_sha256": hashlib.sha256(ACTOR.encode()).hexdigest(),
        "budget_caps": operator.profile_budget_caps(PROFILE),
        "source_sha256": sources,
    }
    (folder / "approval.json").write_text(json.dumps(approval), encoding="utf-8")
    return folder, root, approval


def _real_git_r13_scope(tmp_path):
    folder = tmp_path / "packet"
    root = tmp_path / "approved-source"
    folder.mkdir()
    root.mkdir()
    contract = b"synthetic R13 session contract"
    (folder / "TASK.md").write_bytes(contract)
    for name in sorted(session.R13_SOURCE_PATHS):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())

    git = "D:/Git/cmd/git.exe" if sys.platform == "win32" else "git"
    subprocess.run([git, "init", "--quiet", "--initial-branch=main"], cwd=root, check=True)
    subprocess.run(
        [
            git,
            "-c",
            "user.name=R13 Test",
            "-c",
            "user.email=r13@test.invalid",
            "add",
            "--",
            *sorted(session.R13_SOURCE_PATHS),
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            git,
            "-c",
            "user.name=R13 Test",
            "-c",
            "user.email=r13@test.invalid",
            "commit",
            "--quiet",
            "-m",
            "synthetic approved R13 sources",
        ],
        cwd=root,
        check=True,
    )
    head = (
        subprocess.run([git, "rev-parse", "HEAD"], cwd=root, capture_output=True, check=True)
        .stdout.decode()
        .strip()
    )
    sources = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in sorted(session.R13_SOURCE_PATHS)
    }
    approval = {
        "schema_version": session.R13_APPROVAL_SCHEMA,
        "profile": PROFILE.name,
        "status": "EXACT_SCOPE_APPROVED",
        "head": head,
        "workflow_head": head,
        "contract_sha256": hashlib.sha256(contract).hexdigest(),
        "scope": operator.target_scope_manifest(PROFILE),
        "scope_digest": operator.profile_scope_digest(PROFILE),
        "actor_sha256": hashlib.sha256(ACTOR.encode()).hexdigest(),
        "budget_caps": operator.profile_budget_caps(PROFILE),
        "source_sha256": sources,
    }
    (folder / "approval.json").write_text(json.dumps(approval), encoding="utf-8")
    return folder, root, approval, head


def _fresh_session_sender(current, actor_id, sent):
    def sender(method, url, headers, body):
        path = url.split("gnvzjvgfsxfjgldatbwt.supabase.co", 1)[-1]
        decoded = json.loads(body.decode()) if body else None
        sent.append((method, path, decoded))
        role = "anonymous" if "Authorization" not in headers else current["phase"]
        if path == operator.EDGE_PATH:
            if current["phase"] == "dispatch":
                return HttpResponse(
                    202,
                    json.dumps(
                        {
                            "job_id": PROFILE.job_id,
                            "status": "dispatched",
                            "created": False,
                        }
                    ).encode(),
                )
            if role == "anonymous":
                return HttpResponse(401, b'{"error_code":"AUTH_REQUIRED"}')
            return HttpResponse(403, b'{"code":"OWNER_REQUIRED"}')
        if "/rpc/" in path:
            return HttpResponse(403, b'{"code":"42501"}')
        if path.startswith("/rest/v1/workspaces?"):
            if role in {"anonymous", "nonmember"}:
                return HttpResponse(200, b"[]")
            return HttpResponse(
                200,
                json.dumps(
                    [
                        {
                            "id": PROFILE.workspace_id,
                            "name": PROFILE.workspace_name,
                        }
                    ]
                ).encode(),
            )
        if path.startswith("/rest/v1/automation_jobs?") and method == "POST":
            if role != "owner":
                return HttpResponse(403, b'{"code":"42501"}')
            row = dict(decoded)
            row.update(attempt_count=0, runner_id=None, lease_expires_at=None, heartbeat_at=None)
            return HttpResponse(201, json.dumps([row]).encode())
        if path.startswith("/rest/v1/automation_jobs?") and method == "GET":
            row = operator._job_insert(PROFILE)
            row.update(
                requested_by=actor_id,
                attempt_count=0,
                runner_id=None,
                lease_expires_at=None,
                heartbeat_at=None,
            )
            return HttpResponse(200, json.dumps([row]).encode())
        raise AssertionError(f"unexpected synthetic route: {path}")

    return sender


def test_fresh_session_approval_binds_exact_head_sources_actor_and_caps(tmp_path, monkeypatch):
    folder, root, approval = _r13_approval_fixture(tmp_path)
    checked = []
    monkeypatch.setattr(
        session,
        "_check_clean_head",
        lambda target, head: checked.append((target, head)),
    )
    assert (
        session.check_scope(folder, root)
        == hashlib.sha256((folder / "approval.json").read_bytes()).hexdigest()
    )
    assert checked == [(root, HEAD)]
    loaded = session._load_scope(folder, root)
    assert loaded.profile is PROFILE
    assert loaded.workflow_head == HEAD
    assert loaded.actor_sha256 == approval["actor_sha256"]


def test_fresh_session_runs_all_phases_against_clean_git_scope_and_actor(tmp_path):
    folder, root, _approval, head = _real_git_r13_scope(tmp_path)
    loaded = session._load_scope(folder, root)
    now = int(session.time.time())
    context = {
        "user_uuid": ACTOR,
        "expires_at": now + 900,
        "public_key": "synthetic-public-key",
        "access_token": "synthetic-verified-access-token",
    }
    session._validate_session_context(context, loaded, now=now)
    ledger = operator.OperatorLedger(tmp_path / "operator.json", scope=PROFILE)
    current = {"role": "anonymous", "phase": "nonmember"}
    sent = []
    sender = _fresh_session_sender(current, ACTOR, sent)

    def validate():
        return session.check_scope(folder, root)

    for phase in session.PHASES:
        current["phase"] = phase
        if phase == "nonmember":
            current["role"] = "anonymous"
        elif phase == "reviewer":
            current["role"] = "reviewer"
        else:
            current["role"] = "owner"
        session.execute_phase(
            phase,
            context,
            ledger,
            sender,
            validate_scope=validate,
            scope_digest=loaded.digest,
            scope=PROFILE,
            workflow_head=head,
        )
        assert validate() == loaded.digest

    assert ledger.data["counts"] == {
        "role_total": 15,
        "role_by_name": PROFILE.role_caps,
        "edge_negative": 3,
        "edge_positive": 1,
        "total": 19,
    }
    assert len(sent) == 19
    assert ledger.data["positive_result"]["job_status"] == "dispatched"


@pytest.mark.parametrize("change", ["approval", "source"])
def test_fresh_session_rechecks_real_approval_before_next_send(tmp_path, change):
    folder, root, approval, _head = _real_git_r13_scope(tmp_path)
    loaded = session._load_scope(folder, root)
    now = int(session.time.time())
    context = {
        "user_uuid": ACTOR,
        "expires_at": now + 900,
        "public_key": "synthetic-public-key",
        "access_token": "synthetic-verified-access-token",
    }
    session._validate_session_context(context, loaded, now=now)
    ledger = operator.OperatorLedger(tmp_path / f"{change}-operator.json", scope=PROFILE)
    sent = []

    def change_scope_after_first_send(method, url, headers, body):
        response = _fresh_session_sender({"role": "anonymous", "phase": "nonmember"}, ACTOR, [])(
            method, url, headers, body
        )
        sent.append(url)
        if len(sent) == 1:
            if change == "approval":
                changed = dict(approval)
                changed["scope_digest"] = "0" * 64
                (folder / "approval.json").write_text(json.dumps(changed), encoding="utf-8")
            else:
                source = root / "scripts/api_chain_synthetic_pilot.py"
                source.write_bytes(source.read_bytes() + b"\nchanged after approval\n")
        return response

    with pytest.raises(
        ValueError, match=("R13_SCOPE_BLOCKED|SOURCE_BLOCKED|EXACT_HEAD_CHANGED|ROLE_INCOMPLETE")
    ):
        session.execute_phase(
            "nonmember",
            context,
            ledger,
            change_scope_after_first_send,
            validate_scope=lambda: session.check_scope(folder, root),
            scope_digest=loaded.digest,
            scope=PROFILE,
            workflow_head=loaded.workflow_head,
        )
    assert len(sent) == 1
    assert ledger.data["stop_forward"] is True


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ("scope_digest", "R13_SCOPE_BLOCKED"),
        ("mixed_job", "R13_SCOPE_BLOCKED"),
        ("workflow_head", "R13_SCOPE_BLOCKED"),
        ("actor", "R13_SCOPE_BLOCKED"),
        ("bool_cap", "R13_SCOPE_BLOCKED"),
        ("source_hash", "SOURCE_BLOCKED"),
    ],
)
def test_fresh_session_rejects_tampered_scope_hash_actor_and_caps(
    tmp_path, monkeypatch, change, error
):
    folder, root, approval = _r13_approval_fixture(tmp_path)
    monkeypatch.setattr(session, "_check_clean_head", lambda *_: None)
    if change == "scope_digest":
        approval["scope_digest"] = "0" * 64
    elif change == "mixed_job":
        approval["scope"]["job"]["id"] = operator.JOB_ID
    elif change == "workflow_head":
        approval["workflow_head"] = "c" * 40
    elif change == "actor":
        approval["actor_sha256"] = "not-an-actor-hash"
    elif change == "bool_cap":
        approval["budget_caps"]["role_total"] = True
    else:
        approval["source_sha256"]["scripts/api_chain_synthetic_pilot.py"] = "0" * 64
    (folder / "approval.json").write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        session.check_scope(folder, root)


def test_fresh_session_actor_expiry_and_marker_are_tied_to_approved_principal():
    actor_hash = hashlib.sha256(ACTOR.encode()).hexdigest()
    approved = session.SessionApproval("digest", PROFILE, HEAD, actor_hash)
    session._validate_session_context({"user_uuid": ACTOR, "expires_at": 1500}, approved, now=1000)
    with pytest.raises(ValueError, match="ACTOR_BLOCKED"):
        session._validate_session_context(
            {"user_uuid": "20000000-0000-4000-8000-000000000002", "expires_at": 1500},
            approved,
            now=1000,
        )
    with pytest.raises(ValueError, match="SESSION_TOO_SHORT"):
        session._validate_session_context(
            {"user_uuid": ACTOR, "expires_at": 1359}, approved, now=1000
        )
    with pytest.raises(ValueError, match="SESSION_EXPIRED"):
        session._validate_session_context(
            {"user_uuid": ACTOR, "expires_at": True}, approved, now=1000
        )

    assert session.command(
        {"phase": "dispatch", "marker_sha": HEAD},
        "dispatch",
        None,
        workflow_head=HEAD,
    )
    with pytest.raises(ValueError, match="MARKER_BLOCKED"):
        session.command(
            {"phase": "dispatch", "marker_sha": "c" * 40},
            "dispatch",
            None,
            workflow_head=HEAD,
        )
    assert session.command(
        {"phase": "dispatch", "marker_sha": session.WORKFLOW_HEAD},
        "dispatch",
        None,
    )


def test_fresh_preflight_rejects_recovery_duplicates_and_mixed_job_receipts(tmp_path):
    environment = fresh_environment(preflight=True)
    fresh_history = history_bytes(fresh_run())
    receipt = pilot.preflight(
        environment,
        tmp_path / "valid.json",
        lambda _token: fresh_history,
    )
    assert receipt["status"] == "PREFLIGHT_PASS"
    worker_environment = fresh_environment()
    pilot.validate_preflight_receipt(worker_environment, receipt, status="PREFLIGHT_PASS")

    mixed = dict(receipt, job_id=operator.JOB_ID)
    with pytest.raises(pilot.PilotBlocked, match="PROFILE_MISMATCH"):
        pilot.validate_preflight_receipt(worker_environment, mixed, status="PREFLIGHT_PASS")

    sent = []
    blocked_recovery = pilot.preflight(
        environment,
        tmp_path / "recovery.json",
        lambda _token: sent.append("history"),
        recover_from_run=str(pilot.RECOVERY_RUN_ID),
    )
    assert blocked_recovery["error_code"] == "PILOT_FRESH_R13_RECOVERY_BLOCKED"
    assert sent == []

    duplicate = pilot.preflight(
        environment,
        tmp_path / "duplicate.json",
        lambda _token: history_bytes(fresh_run(), fresh_run(id=85), total=2),
    )
    assert duplicate["error_code"] == "PILOT_HISTORY_AMBIGUOUS"
    unknown = fresh_environment(preflight=True)
    unknown["JOB_ID"] = "c8841b3c-5740-5b0a-aeaf-9dad5f5f17a6"
    sent.clear()
    blocked_unknown = pilot.preflight(
        unknown, tmp_path / "unknown.json", lambda _token: sent.append("history")
    )
    assert blocked_unknown["error_code"] == "PILOT_CONTEXT_BLOCKED"
    assert sent == []


@pytest.mark.parametrize("heartbeat_count", [20, 22])
def test_fresh_worker_latches_scope_and_verifies_bounded_lease_cycle(
    tmp_path, monkeypatch, heartbeat_count
):
    receipt = pilot.new_worker_receipt(HEAD, "84", scope=PROFILE)
    receipt["worker_started_monotonic"] = 400.0
    monkeypatch.setattr(pilot.time, "monotonic", lambda: 1000.0)
    calls = []

    job_row = {
        "id": PROFILE.job_id,
        "workspace_id": PROFILE.workspace_id,
        "type": PROFILE.job_type,
        "status": "dispatched",
        "idempotency_key": PROFILE.idempotency_key,
        "payload_json": PROFILE.payload,
        "max_attempts": 1,
        "attempt_count": 0,
        "runner_id": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }
    claim_row = {
        "claimed": True,
        "run_id": WORKER_RUN_ID,
        "job_id": PROFILE.job_id,
        "workspace_id": PROFILE.workspace_id,
        "job_type": PROFILE.job_type,
        "payload_json": PROFILE.payload,
        "attempt": 1,
        "runner_id": PROFILE.runner_id,
        "lease_expires_at": "2030-01-01T00:10:00+00:00",
    }

    def sender(method, url, headers, body):
        del headers
        parsed_path = url.split("gnvzjvgfsxfjgldatbwt.supabase.co", 1)[-1]
        value = json.loads(body.decode()) if body else None
        calls.append((method, parsed_path, value))
        if parsed_path == pilot._job_preflight_path(PROFILE):
            return HttpResponse(200, json.dumps([job_row]).encode())
        if parsed_path == pilot._state_preflight_path(PROFILE):
            return HttpResponse(200, b"[]")
        if parsed_path.endswith("/claim_automation_job_run"):
            return HttpResponse(200, json.dumps([claim_row]).encode())
        if parsed_path.endswith("/heartbeat_automation_job"):
            return HttpResponse(
                200,
                json.dumps(
                    [
                        {
                            "job_id": PROFILE.job_id,
                            "workspace_id": PROFILE.workspace_id,
                            "run_id": WORKER_RUN_ID,
                            "runner_id": PROFILE.runner_id,
                            "lease_expires_at": "2030-01-01T00:10:30+00:00",
                        }
                    ]
                ).encode(),
            )
        if parsed_path.endswith("/finish_automation_job_run"):
            return HttpResponse(200, b'[{"status":"succeeded"}]')
        raise AssertionError(f"unexpected worker route: {parsed_path}")

    transport = pilot.WorkerApiTransport(receipt, tmp_path / "worker.json", sender, scope=PROFILE)
    client = transport.client("synthetic-service-key")
    assert pilot.worker_preflight(client, scope=PROFILE)["job_id"] == PROFILE.job_id
    pilot_client = pilot.PilotApiClient(client)
    claim = pilot_client.claim_job_run(PROFILE.job_id, PROFILE.runner_id)
    for _ in range(heartbeat_count):
        pilot_client.heartbeat_job(PROFILE.job_id, PROFILE.runner_id)
    pilot_client.finish_job_run(
        claim.run_id,
        PROFILE.runner_id,
        "succeeded",
        records_read=0,
        error_code=None,
        duration_ms=650000,
    )
    receipt.update(
        status="WORKER_RETURNED",
        finish_result="succeeded",
        cli_outcome={"status": "succeeded", "records_read": 0, "duration_ms": 650000},
    )

    pilot._verify_worker(receipt, 0, scope=PROFILE)
    assert receipt["request_count"] == 4 + heartbeat_count
    assert receipt["counts"] == {
        "job_preflight": 1,
        "state_preflight": 1,
        "claim": 1,
        "heartbeat": heartbeat_count,
        "finish": 1,
    }
    assert len(calls) == 4 + heartbeat_count
    assert receipt["intents"][-1]["elapsed_seconds"] == 600.0

    mutated = pilot.new_worker_receipt(HEAD, "84", scope=PROFILE)
    blocked_sender = Mock()
    latched = pilot.WorkerApiTransport(
        mutated, tmp_path / "mutated.json", blocked_sender, scope=PROFILE
    )
    mutated["job_id"] = operator.JOB_ID
    with pytest.raises(pilot.PilotBlocked, match="PROFILE_MISMATCH"):
        latched("GET", f"{pilot.BASE_URL}{pilot._job_preflight_path(PROFILE)}", {}, None)
    blocked_sender.assert_not_called()

    replay = pilot.new_worker_receipt(HEAD, "84", scope=PROFILE)
    replay["request_count"] = 1
    replay["counts"]["claim"] = 1
    replay["intents"] = [{"ordinal": 1, "kind": "claim"}]
    with pytest.raises(pilot.PilotBlocked, match="RECEIPT_REPLAY_BLOCKED"):
        pilot.WorkerApiTransport(replay, tmp_path / "replay.json", Mock(), scope=PROFILE)


def test_fresh_worker_runs_async_hold_and_keeps_profile_when_cleanup_is_uncertain(
    tmp_path, monkeypatch
):
    import asyncio as real_asyncio

    from mindx_runner import browser_driver, cli

    receipt_file = tmp_path / "worker" / "receipt.json"
    preflight_environment = fresh_environment(preflight=True)
    preflight = pilot.preflight(
        preflight_environment,
        receipt_file,
        lambda _token: history_bytes(fresh_run()),
    )
    assert preflight["status"] == "PREFLIGHT_PASS"

    environment = fresh_environment()
    environment["SUPABASE_SECRET_KEY"] = "synthetic-runner-key"
    environment["GITHUB_ACTIONS"] = "true"
    chromium = tmp_path / "chrome.exe"
    chromium.write_bytes(b"synthetic executable marker")
    profile = receipt_file.parent / "profile"
    fake_clock = {"seconds": 100.0}
    time_source = SimpleNamespace(monotonic=lambda: fake_clock["seconds"])
    loop_holder = {}
    heartbeat_event = {}
    heartbeat_count = []
    sent = []
    sessions = []

    class FakeSessionManager:
        def get_all_targets(self):
            return {"target-1": SimpleNamespace(url="about:blank", target_type="page")}

    class FakeManagedBrowserSession:
        def __init__(self, **options):
            self.options = options
            self.session_manager = FakeSessionManager()
            self.started = False
            self.stopped = False
            user_data_dir = Path(options["user_data_dir"])
            user_data_dir.mkdir(parents=True, exist_ok=True)
            (user_data_dir / "managed-profile.marker").write_text(
                "synthetic profile", encoding="utf-8"
            )
            sessions.append(self)

        async def start(self):
            self.started = True

        async def stop(self):
            self.stopped = True

    async def skip_network_guard(_session):
        return None

    async def accelerated_hold(seconds):
        assert seconds == pilot.HOLD_SECONDS
        loop_holder["loop"] = real_asyncio.get_running_loop()
        event = real_asyncio.Event()
        heartbeat_event["event"] = event
        for _ in range(22):
            await event.wait()
            event.clear()
            fake_clock["seconds"] += 30

    def sender(method, url, headers, body):
        del headers
        path = url.split("gnvzjvgfsxfjgldatbwt.supabase.co", 1)[-1]
        value = json.loads(body.decode()) if body else None
        sent.append((method, path, value))
        if path == pilot._job_preflight_path(PROFILE):
            return HttpResponse(
                200,
                json.dumps(
                    [
                        {
                            "id": PROFILE.job_id,
                            "workspace_id": PROFILE.workspace_id,
                            "type": PROFILE.job_type,
                            "status": "dispatched",
                            "idempotency_key": PROFILE.idempotency_key,
                            "payload_json": PROFILE.payload,
                            "max_attempts": 1,
                            "attempt_count": 0,
                            "runner_id": None,
                            "lease_expires_at": None,
                            "heartbeat_at": None,
                        }
                    ]
                ).encode(),
            )
        if path == pilot._state_preflight_path(PROFILE):
            return HttpResponse(200, b"[]")
        if path.endswith("/claim_automation_job_run"):
            return HttpResponse(
                200,
                json.dumps(
                    [
                        {
                            "claimed": True,
                            "run_id": WORKER_RUN_ID,
                            "job_id": PROFILE.job_id,
                            "workspace_id": PROFILE.workspace_id,
                            "job_type": PROFILE.job_type,
                            "payload_json": PROFILE.payload,
                            "attempt": 1,
                            "runner_id": PROFILE.runner_id,
                            "lease_expires_at": "2030-01-01T00:10:00+00:00",
                        }
                    ]
                ).encode(),
            )
        if path.endswith("/heartbeat_automation_job"):
            heartbeat_count.append(value)
            loop_holder["loop"].call_soon_threadsafe(heartbeat_event["event"].set)
            return HttpResponse(
                200,
                json.dumps(
                    [
                        {
                            "job_id": PROFILE.job_id,
                            "workspace_id": PROFILE.workspace_id,
                            "run_id": WORKER_RUN_ID,
                            "runner_id": PROFILE.runner_id,
                            "lease_expires_at": "2030-01-01T00:10:30+00:00",
                        }
                    ]
                ).encode(),
            )
        if path.endswith("/finish_automation_job_run"):
            return HttpResponse(
                200,
                json.dumps(
                    [
                        {
                            "status": "succeeded",
                            "job_id": PROFILE.job_id,
                            "workspace_id": PROFILE.workspace_id,
                            "run_id": WORKER_RUN_ID,
                        }
                    ]
                ).encode(),
            )
        raise AssertionError(f"unexpected synthetic worker route: {path}")

    original_defaults_check = pilot.cli_defaults_ok

    def defaults_check_then_accelerate_heartbeat():
        assert original_defaults_check()
        monkeypatch.setattr(cli, "HEARTBEAT_INTERVAL_SECONDS", 0.005)
        return True

    class FakeProcess:
        pid = 4242
        returncode = 0

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            del timeout
            return self.returncode

        def kill(self):
            raise AssertionError("synthetic worker already exited")

    process = FakeProcess()

    def launch_worker(_command, *, env, **_kwargs):
        assert pilot._worker(env, receipt_file, str(chromium))["status"] == "WORKER_RETURNED"
        return process

    monkeypatch.setattr(pilot.importlib.metadata, "version", lambda _name: "0.13.6")
    monkeypatch.setattr(pilot, "time", time_source)
    monkeypatch.setattr(cli, "time", time_source)
    monkeypatch.setattr(
        pilot,
        "asyncio",
        SimpleNamespace(run=real_asyncio.run, sleep=accelerated_hold),
    )
    real_worker_transport = pilot.WorkerApiTransport
    monkeypatch.setattr(
        pilot,
        "WorkerApiTransport",
        lambda receipt, file, *, scope: real_worker_transport(
            receipt, file, sender=sender, scope=scope
        ),
    )
    monkeypatch.setattr(pilot, "cli_defaults_ok", defaults_check_then_accelerate_heartbeat)
    monkeypatch.setattr(
        browser_driver.ReadonlyBrowserSession,
        "_install_target_guard",
        skip_network_guard,
    )
    browser_module = importlib.import_module("browser_use.browser")
    monkeypatch.setattr(browser_module, "BrowserSession", FakeManagedBrowserSession)
    monkeypatch.setattr(pilot.subprocess, "Popen", launch_worker)
    monkeypatch.setattr(
        pilot,
        "_stop_owned_processes",
        lambda _parent, _owned, _process: ([{"pid": 4343, "created": 12.0, "name": "chrome"}], []),
    )
    monkeypatch.setitem(
        sys.modules,
        "psutil",
        SimpleNamespace(Process=lambda _pid: SimpleNamespace(create_time=lambda: 1.0)),
    )

    previous_logging_disable = importlib.import_module("logging").root.manager.disable
    try:
        result = pilot.supervise(environment, receipt_file, str(chromium))
    finally:
        importlib.import_module("logging").disable(previous_logging_disable)

    persisted = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert len(sessions) == 1 and sessions[0].started and sessions[0].stopped
    assert Path(sessions[0].options["user_data_dir"]) == profile
    assert len(heartbeat_count) == 22
    assert len(sent) == 26
    assert result == persisted
    assert result["status"] == "BLOCKED"
    assert result["error_code"] == "PILOT_CLEANUP_UNCONFIRMED"
    assert result["request_count"] == 26
    assert result["counts"]["heartbeat"] == 22
    assert result["finish_result"] == "succeeded"
    assert result["history_outcome"] == "ONE_FIXED_JOB_RUN_CONFIRMED"
    assert result["owned_profile_removed"] is False
    assert result["residual_processes"] == [{"pid": 4343, "created": 12.0, "name": "chrome"}]
    assert profile.exists()
    assert (profile / "managed-profile.marker").read_text(encoding="utf-8") == "synthetic profile"
