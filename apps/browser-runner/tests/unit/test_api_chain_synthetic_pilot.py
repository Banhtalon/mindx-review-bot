"""API-chain pilot contracts. All identities and transport responses are synthetic."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps/browser-runner/src"))
sys.path.insert(0, str(ROOT / "scripts"))

BASE_URL = "https://gnvzjvgfsxfjgldatbwt.supabase.co"
WORKSPACE_ID = "50318d02-6840-457d-b5a6-0870e7a308a4"
JOB_ID = "a3fed449-7fac-422f-a3a7-9b22be678c12"
RUN_ID = "ce2d8c98-bd56-5e33-99de-8ef487e4a2ab"
JOB_TYPE = "sync_teaching"
IDEMPOTENCY_KEY = "phase2-api-chain-20261006-r1"
PAYLOAD = {"synthetic": True, "pilot_id": IDEMPOTENCY_KEY, "case": "success"}
RUNNER_ID = "api-chain-synthetic-r1"
HEAD = "a" * 40


def load_script(name: str):
    path = ROOT / "scripts" / name
    assert path.is_file(), f"expected the new {name} implementation"
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def workflow_environment():
    return {
        "GITHUB_REPOSITORY": "Banhtalon/mindx-review-bot",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "42",
        "GITHUB_SHA": HEAD,
        "MINDX_API_CHAIN_PILOT_APPROVAL_SHA": HEAD,
        "JOB_ID": JOB_ID,
        "JOB_TYPE": JOB_TYPE,
        "GITHUB_TOKEN": "synthetic-read-only-token",
    }


def history_bytes(*runs, total=None):
    return json.dumps(
        {"total_count": len(runs) if total is None else total, "workflow_runs": runs}
    ).encode()


def current_run(**changes):
    run = {
        "id": 42,
        "display_title": f"API chain synthetic {JOB_ID}",
        "name": "spike0-dispatch-probe",
        "path": ".github/workflows/spike0-dispatch-probe.yml",
        "head_sha": HEAD,
        "head_branch": "main",
        "event": "workflow_dispatch",
        "run_attempt": 1,
        "run_number": 17,
    }
    run.update(changes)
    return run


def job_row(**changes):
    row = {
        "id": JOB_ID,
        "workspace_id": WORKSPACE_ID,
        "type": JOB_TYPE,
        "status": "dispatched",
        "idempotency_key": IDEMPOTENCY_KEY,
        "payload_json": PAYLOAD,
        "max_attempts": 1,
        "attempt_count": 0,
        "runner_id": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }
    row.update(changes)
    return row


def test_pilot_api_client_delegates_only_the_three_real_rpc_methods():
    pilot = load_script("api_chain_synthetic_pilot.py")
    delegate = Mock()
    delegate.claim_job_run.return_value = object()
    delegate.heartbeat_job.return_value = object()
    delegate.finish_job_run.return_value = object()
    client = pilot.PilotApiClient(delegate)

    assert client.claim_job_run(JOB_ID, RUNNER_ID) is delegate.claim_job_run.return_value
    assert client.heartbeat_job(JOB_ID, RUNNER_ID) is delegate.heartbeat_job.return_value
    assert (
        client.finish_job_run(
            RUN_ID, RUNNER_ID, "succeeded", records_read=0, error_code=None, duration_ms=650000
        )
        is delegate.finish_job_run.return_value
    )
    assert not hasattr(client, "load_active_browser_state")
    assert "__getattr__" not in type(client).__dict__
    delegate.claim_job_run.assert_called_once_with(JOB_ID, RUNNER_ID)
    delegate.heartbeat_job.assert_called_once_with(JOB_ID, RUNNER_ID)
    delegate.finish_job_run.assert_called_once()


def test_history_guard_requires_a_complete_single_fixed_job_dispatch_not_run_number_one(
    tmp_path,
):
    pilot = load_script("api_chain_synthetic_pilot.py")
    unrelated = current_run(id=41, display_title="older other job", run_number=3)
    reads = []
    result = pilot.preflight(
        workflow_environment(),
        tmp_path / "receipt.json",
        lambda token: reads.append(token) or history_bytes(unrelated, current_run(), total=2),
    )

    assert result["status"] == "PREFLIGHT_PASS"
    assert result["history_reads"] == 1
    assert reads == ["synthetic-read-only-token"]

    blocked = pilot.preflight(
        workflow_environment(),
        tmp_path / "incomplete.json",
        lambda _: history_bytes(current_run(), total=101),
    )
    assert blocked["status"] == "BLOCKED"
    assert blocked["history_reads"] == 1


def test_context_rejects_wrong_scope_before_history_send(tmp_path):
    pilot = load_script("api_chain_synthetic_pilot.py")
    for key, value in [
        ("GITHUB_REPOSITORY", "someone/else"),
        ("GITHUB_REF", "refs/heads/other"),
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("MINDX_API_CHAIN_PILOT_APPROVAL_SHA", "b" * 40),
        ("JOB_ID", "00000000-0000-4000-8000-000000000001"),
        ("JOB_TYPE", "read_lms_pending"),
    ]:
        env = {**workflow_environment(), key: value}
        transport = Mock(return_value=history_bytes(current_run()))
        result = pilot.preflight(env, tmp_path / f"bad-{key}.json", transport)
        assert result["status"] == "BLOCKED"
        transport.assert_not_called()


def test_worker_preflight_requires_dispatched_job_and_empty_state_before_claim():
    pilot = load_script("api_chain_synthetic_pilot.py")
    from mindx_runner.supabase_client import HttpResponse, SupabaseRunnerClient

    calls = []

    def sender(method, url, headers, body):
        del headers, body
        calls.append((method, url))
        if "/automation_jobs?" in url:
            return HttpResponse(200, json.dumps([job_row()]).encode())
        if "/browser_state_versions?" in url:
            return HttpResponse(200, b"[]")
        raise AssertionError("unexpected request")

    client = SupabaseRunnerClient(BASE_URL, "synthetic-service-key", transport=sender)
    checked = pilot.worker_preflight(client)
    assert checked["job_id"] == JOB_ID and checked["status"] == "dispatched"
    assert len(calls) == 2 and all(method == "GET" for method, _ in calls)

    calls.clear()

    def queued_sender(method, url, headers, body):
        del headers, body
        calls.append((method, url))
        if "/automation_jobs?" in url:
            return HttpResponse(200, json.dumps([job_row(status="queued")]).encode())
        raise AssertionError("state request must not follow an invalid job")

    queued_client = SupabaseRunnerClient(
        BASE_URL, "synthetic-service-key", transport=queued_sender
    )
    with pytest.raises(pilot.PilotBlocked, match="JOB_STATE_BLOCKED"):
        pilot.worker_preflight(queued_client)
    assert len(calls) == 1 and calls[0][0] == "GET"


def test_unknown_worker_transport_failure_consumes_one_request_and_redacts(tmp_path):
    pilot = load_script("api_chain_synthetic_pilot.py")
    receipt = pilot.new_worker_receipt(HEAD, "42")
    sender = Mock(side_effect=OSError("private-token-and-response-must-not-appear"))
    transport = pilot.WorkerApiTransport(receipt, tmp_path / "receipt.json", sender)

    with pytest.raises(pilot.PilotBlocked):
        pilot.worker_preflight(transport.client("synthetic-service-key"))

    persisted = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))
    assert persisted["request_count"] == 1
    assert persisted["intents"][0]["outcome"] == "UNKNOWN"
    assert sender.call_count == 1
    assert "private-token" not in json.dumps(persisted)
    with pytest.raises(pilot.PilotBlocked):
        pilot.worker_preflight(transport.client("synthetic-service-key"))
    assert sender.call_count == 1


def test_server_lease_snapshots_preserve_the_real_http_response(tmp_path):
    pilot = load_script("api_chain_synthetic_pilot.py")
    from mindx_runner.supabase_client import HttpResponse

    response = HttpResponse(
        200,
        json.dumps(
            [
                {
                    "claimed": True,
                    "run_id": RUN_ID,
                    "job_id": JOB_ID,
                    "workspace_id": WORKSPACE_ID,
                    "job_type": JOB_TYPE,
                    "payload_json": PAYLOAD,
                    "attempt": 1,
                    "runner_id": RUNNER_ID,
                    "lease_expires_at": "2026-10-06T12:10:00+00:00",
                }
            ]
        ).encode(),
    )
    sender = Mock(return_value=response)
    receipt = pilot.new_worker_receipt(HEAD, "42")
    transport = pilot.WorkerApiTransport(receipt, tmp_path / "receipt.json", sender)
    actual = transport(
        "POST",
        f"{BASE_URL}/rest/v1/rpc/claim_automation_job_run",
        {},
        json.dumps(
            {"target_job_id": JOB_ID, "target_runner_id": RUNNER_ID},
            separators=(",", ":"), sort_keys=True,
        ).encode(),
    )

    assert actual is response
    assert receipt["server_snapshots"][0] == {
        "kind": "claim",
        "job_id": JOB_ID,
        "run_id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "runner_id": RUNNER_ID,
        "attempt": 1,
        "lease_expires_at": "2026-10-06T12:10:00+00:00",
    }


def test_real_supabase_client_completes_only_the_bounded_rpc_cycle_and_forwards_auth(tmp_path):
    pilot = load_script("api_chain_synthetic_pilot.py")
    from mindx_runner.supabase_client import HttpResponse

    def row(**changes):
        value = {
            "claimed": True,
            "run_id": RUN_ID,
            "job_id": JOB_ID,
            "workspace_id": WORKSPACE_ID,
            "job_type": JOB_TYPE,
            "payload_json": PAYLOAD,
            "attempt": 1,
            "runner_id": RUNNER_ID,
            "lease_expires_at": "2026-10-06T12:10:00+00:00",
        }
        value.update(changes)
        return value

    sent = []

    def sender(method, url, headers, body):
        sent.append((method, url, headers, json.loads(body)))
        if url.endswith("/claim_automation_job_run"):
            response = [row()]
        elif url.endswith("/heartbeat_automation_job"):
            response = [{"job_id": JOB_ID, "runner_id": RUNNER_ID,
                         "lease_expires_at": "2026-10-06T12:10:30+00:00"}]
        elif url.endswith("/finish_automation_job_run"):
            response = [{"status": "succeeded"}]
        else:
            raise AssertionError("real client escaped the RPC allowlist")
        return HttpResponse(200, json.dumps(response).encode())

    receipt = pilot.new_worker_receipt(HEAD, "42")
    receipt["worker_started_monotonic"] = pilot.time.monotonic() - 601
    receipt_path = tmp_path / "receipt.json"
    transport = pilot.WorkerApiTransport(receipt, receipt_path, sender)
    client = pilot.PilotApiClient(transport.client("synthetic-service-key"))

    claim = client.claim_job_run(JOB_ID, RUNNER_ID)
    client.heartbeat_job(JOB_ID, RUNNER_ID)
    client.finish_job_run(
        claim.run_id, RUNNER_ID, "succeeded", records_read=0,
        error_code=None, duration_ms=650000,
    )

    assert len(sent) == 3
    assert [url.rsplit("/", 1)[-1] for _, url, _, _ in sent] == [
        "claim_automation_job_run", "heartbeat_automation_job", "finish_automation_job_run"
    ]
    assert all(headers["apikey"] == "synthetic-service-key" for _, _, headers, _ in sent)
    assert all(headers["Authorization"] == "Bearer synthetic-service-key"
               for _, _, headers, _ in sent)
    assert sent[-1][3] == {
        "target_run_id": RUN_ID,
        "target_runner_id": RUNNER_ID,
        "target_status": "succeeded",
        "target_records_read": 0,
        "target_error_code": None,
        "target_duration_ms": 650000,
    }
    assert len(receipt["server_snapshots"]) == 3
    assert receipt["finish_result"] == "succeeded"
    assert receipt["intents"][1]["elapsed_seconds"] >= 600


@pytest.mark.parametrize("budget", ["kind", "total"])
def test_request_budget_blocks_before_second_send(tmp_path, budget):
    pilot = load_script("api_chain_synthetic_pilot.py")
    sender = Mock()
    receipt = pilot.new_worker_receipt(HEAD, "42")
    if budget == "kind":
        receipt["counts"]["job_preflight"] = 1
    else:
        receipt["request_count"] = pilot.MAX_REQUESTS
    transport = pilot.WorkerApiTransport(receipt, tmp_path / "receipt.json", sender)

    with pytest.raises(pilot.PilotBlocked, match="REQUEST_BUDGET_EXCEEDED"):
        transport(
            "GET", f"{BASE_URL}{pilot.JOB_PREFLIGHT_PATH}", {}, None
        )
    sender.assert_not_called()


@pytest.mark.parametrize("kind", ["claim", "heartbeat"])
def test_malformed_lease_metadata_is_redacted_and_blocks_client(tmp_path, kind):
    pilot = load_script("api_chain_synthetic_pilot.py")
    from mindx_runner.supabase_client import HttpResponse

    good_claim = [{
        "claimed": True, "run_id": RUN_ID, "job_id": JOB_ID,
        "workspace_id": WORKSPACE_ID, "job_type": JOB_TYPE, "payload_json": PAYLOAD,
        "attempt": 1, "runner_id": RUNNER_ID,
        "lease_expires_at": "2026-10-06T12:10:00+00:00",
    }]
    bad_claim = [{**good_claim[0], "attempt": True}]
    responses = [
        HttpResponse(200, json.dumps(bad_claim if kind == "claim" else good_claim).encode())
    ]
    if kind == "heartbeat":
        responses.append(HttpResponse(200, json.dumps([{
            "job_id": JOB_ID, "runner_id": RUNNER_ID,
            "lease_expires_at": "not-a-timestamp",
        }]).encode()))

    def sender(*_):
        return responses.pop(0)

    receipt = pilot.new_worker_receipt(HEAD, "42")
    transport = pilot.WorkerApiTransport(receipt, tmp_path / "receipt.json", sender)
    client = transport.client("synthetic-service-key")
    if kind == "claim":
        with pytest.raises(pilot.PilotBlocked, match="RESPONSE_INVALID"):
            client.claim_job_run(JOB_ID, RUNNER_ID)
        invalid_intent = receipt["intents"][0]
    else:
        client.claim_job_run(JOB_ID, RUNNER_ID)
        with pytest.raises(pilot.PilotBlocked, match="RESPONSE_INVALID"):
            client.heartbeat_job(JOB_ID, RUNNER_ID)
        invalid_intent = receipt["intents"][1]

    assert invalid_intent["metadata"] == "MALFORMED_OR_UNAVAILABLE"
    assert len(receipt["server_snapshots"]) == (0 if kind == "claim" else 1)
    assert "not-a-timestamp" not in json.dumps(receipt)


def test_live_empty_browser_state_still_fails_closed():
    from mindx_runner import cli
    from mindx_runner.supabase_client import ClaimedRun, HttpResponse, SupabaseRunnerClient

    client = SupabaseRunnerClient(
        BASE_URL,
        "synthetic-service-key",
        transport=lambda *_: HttpResponse(200, b"[]"),
    )
    config = cli.load_live_config(
        {
            "AUTOMATION_ENABLED": "true",
            "MVP_LMS_WRITE_ENABLED": "false",
            "JOB_ID": JOB_ID,
            "RUNNER_ID": RUNNER_ID,
            "JOB_TYPE": JOB_TYPE,
            "SUPABASE_URL": BASE_URL,
            "SUPABASE_SECRET_KEY": "synthetic-service-key",
            "BROWSER_STATE_ENCRYPTION_KEY": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
        }
    )
    claimed = ClaimedRun(True, RUN_ID, JOB_ID, WORKSPACE_ID, JOB_TYPE, PAYLOAD, 1)
    with pytest.raises(cli.RunnerError, match="STORAGE_STATE_DECRYPT_FAILED"):
        asyncio.run(cli._load_browser_storage_state(client, config, claimed))


def test_operator_freezes_role_matrix_and_refuses_404_as_permission_proof():
    operator = load_script("api_chain_operator.py")
    assert [len(operator.role_probe_requests(role)) for role in operator.ROLES] == [2, 2, 5, 6]
    assert sum(len(operator.role_probe_requests(role)) for role in operator.ROLES) == 15
    from mindx_runner.supabase_client import HttpResponse

    assert not operator.permission_denied(HttpResponse(404, b'{"code":"PGRST202"}'))
    assert operator.permission_denied(HttpResponse(403, b'{"code":"42501"}'))
    assert not operator.permission_denied(HttpResponse(403, b'{"message":"forbidden"}'))
    owner_requests = operator.role_probe_requests("owner")
    insert = owner_requests[1]
    assert insert["method"] == "POST"
    assert insert["path"].startswith("/rest/v1/automation_jobs")
    assert insert["body"] == {
        "id": JOB_ID,
        "workspace_id": WORKSPACE_ID,
        "type": JOB_TYPE,
        "status": "queued",
        "idempotency_key": IDEMPOTENCY_KEY,
        "requested_by": "$AUTH_USER_ID",
        "payload_json": PAYLOAD,
        "max_attempts": 1,
    }
    assert owner_requests[2]["body"] == {
        "target_job_id": JOB_ID, "target_runner_id": RUNNER_ID
    }
    assert operator.EDGE_BODY == {
        "workspace_id": WORKSPACE_ID,
        "type": JOB_TYPE,
        "idempotency_key": IDEMPOTENCY_KEY,
        "payload": PAYLOAD,
    }


def test_operator_caps_and_private_receipt_block_before_sender(tmp_path):
    operator = load_script("api_chain_operator.py")
    sender = Mock(return_value=None)
    ledger = operator.OperatorLedger(tmp_path / "operator.json")
    for _ in range(operator.NEGATIVE_EDGE_CAP):
        ledger.reserve(
            "edge_negative", "reviewer", "POST", "/functions/v1/dispatch-job",
            operator.EDGE_BODY,
        )

    with pytest.raises(operator.OperatorBlocked, match="BUDGET"):
        operator.probe_edge_negative(
            "reviewer",
            {"Authorization": "Bearer synthetic-app-token", "apikey": "synthetic-anon-key"},
            sender,
            ledger,
        )
    sender.assert_not_called()
    persisted = json.dumps(ledger.data)
    assert "$AUTH_USER_ID" not in persisted
    assert "Authorization" not in persisted


def test_operator_role_matrix_uses_only_fake_http_and_redacts_private_identity(tmp_path):
    operator = load_script("api_chain_operator.py")
    from mindx_runner.supabase_client import HttpResponse

    synthetic_user_id = "9e8fcbf5-c7e3-4d8d-9d0e-4abddbc145de"
    sent = []
    job_row = None

    def sender(method, url, headers, body):
        nonlocal job_row
        sent.append((method, url, headers, body))
        role = headers.get("Authorization", "").replace("Bearer synthetic-", "")
        if url.split("?", 1)[0].endswith("/rest/v1/workspaces"):
            rows = (
                [] if role in {"", "nonmember"}
                else [{"id": operator.WORKSPACE_ID, "name": operator.WORKSPACE_NAME}]
            )
            return HttpResponse(200, json.dumps(rows).encode())
        if "/rest/v1/automation_jobs?" in url and method == "POST":
            if role != "owner":
                return HttpResponse(403, b'{"code":"42501"}')
            job_row = {
                "id": operator.JOB_ID,
                "workspace_id": operator.WORKSPACE_ID,
                "type": operator.JOB_TYPE,
                "status": "queued",
                "idempotency_key": operator.IDEMPOTENCY_KEY,
                "requested_by": synthetic_user_id,
                "payload_json": operator.PAYLOAD,
                "max_attempts": 1,
                "attempt_count": 0,
                "runner_id": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
            }
            return HttpResponse(201, json.dumps([job_row]).encode())
        if url.endswith("/rest/v1/automation_jobs?" + operator.JOB_GET_PATH.split("?", 1)[1]):
            return HttpResponse(200, json.dumps([job_row]).encode())
        if "/rest/v1/rpc/" in url:
            status = 401 if role == "" else 403
            return HttpResponse(status, b'{"code":"42501"}')
        raise AssertionError("operator request escaped the fixed synthetic routes")

    ledger = operator.OperatorLedger(tmp_path / "operator.json")
    for role in operator.ROLES:
        headers = (
            {"apikey": "synthetic-anon-key"}
            if role == "anonymous"
            else {"apikey": "synthetic-anon-key", "Authorization": f"Bearer synthetic-{role}"}
        )
        result = operator.run_role_probes(
            role, sender, ledger, auth_headers=headers,
            caller_user_id=None if role == "anonymous" else synthetic_user_id,
        )
        assert result["status"] == "PASS", {
            "role": role, "result": result, "tail": ledger.data["intents"][-3:]
        }

    assert len(sent) == operator.ROLE_TOTAL_CAP == 15
    assert ledger.data["role_matrix_complete"] is True
    receipt = json.dumps(ledger.data)
    assert synthetic_user_id not in receipt
    assert "synthetic-app" not in receipt


def test_positive_edge_requires_all_preconditions_and_fixed_response(tmp_path):
    operator = load_script("api_chain_operator.py")
    from mindx_runner.supabase_client import HttpResponse

    ledger = operator.OperatorLedger(tmp_path / "operator.json")
    sender = Mock(return_value=HttpResponse(
        202, json.dumps({"job_id": JOB_ID, "status": "dispatched", "created": False}).encode()
    ))
    blocked = operator.dispatch_existing_job(
        object(), sender, ledger, marker_sha=HEAD, approved_sha=HEAD, final_scope=True
    )
    assert blocked["status"] == "BLOCKED"
    sender.assert_not_called()


def test_positive_edge_sends_exactly_once_after_frozen_gates(tmp_path):
    operator = load_script("api_chain_operator.py")
    from mindx_runner.supabase_client import HttpResponse

    ledger = operator.OperatorLedger(tmp_path / "operator.json")
    counts = ledger.data["counts"]
    counts["role_total"] = operator.ROLE_TOTAL_CAP
    counts["role_by_name"] = dict(operator.ROLE_CAPS)
    counts["edge_negative"] = operator.NEGATIVE_EDGE_CAP
    counts["total"] = operator.ROLE_TOTAL_CAP + operator.NEGATIVE_EDGE_CAP
    ledger.data["role_matrix_complete"] = True
    ledger.data["owner_job_verified"] = True
    ledger.data["role_results"] = [
        {"role": role, "status": "PASS"} for role, count in operator.ROLE_CAPS.items()
        for _ in range(count)
    ]
    ledger.data["negative_edge_results"] = [
        {"role": "anonymous", "status": "AUTH_GATE_ONLY"},
        {"role": "nonmember", "status": "DENIED_OWNER_REQUIRED"},
        {"role": "reviewer", "status": "DENIED_OWNER_REQUIRED"},
    ]
    sender = Mock(return_value=HttpResponse(
        202, json.dumps({"job_id": JOB_ID, "status": "dispatched", "created": False}).encode()
    ))
    headers = {"Authorization": "Bearer synthetic-app-token", "apikey": "synthetic-anon-key"}

    outcome = operator.dispatch_existing_job(
        headers, sender, ledger, marker_sha=HEAD, approved_sha=HEAD, final_scope=True
    )

    assert outcome["status"] == "PASS"
    assert sender.call_count == 1
    assert sender.call_args.args[0] == "POST"
    assert sender.call_args.args[1] == f"{operator.BASE_URL}{operator.EDGE_PATH}"
    assert json.loads(sender.call_args.args[3]) == operator.EDGE_BODY
    assert "synthetic-app-token" not in json.dumps(ledger.data)


def test_unexpected_accepted_negative_edge_probe_stops_before_positive(tmp_path):
    operator = load_script("api_chain_operator.py")
    from mindx_runner.supabase_client import HttpResponse

    ledger = operator.OperatorLedger(tmp_path / "operator.json")
    sender = Mock(return_value=HttpResponse(202, b'{"job_id":"accepted"}'))
    outcome = operator.probe_edge_negative(
        "reviewer",
        {"Authorization": "Bearer synthetic-app-token", "apikey": "synthetic-anon-key"},
        sender,
        ledger,
    )
    assert outcome["status"] == "BLOCKED_UNEXPECTED_ACCEPTANCE"
    assert ledger.data["stop_forward"] is True
    positive = operator.dispatch_existing_job(
        object(), sender, ledger, marker_sha=HEAD, approved_sha=HEAD, final_scope=True
    )
    assert positive["status"] == "BLOCKED"
    assert sender.call_count == 1


def test_operator_sql_templates_use_private_bind_and_live_cli_waits(tmp_path):
    operator = load_script("api_chain_operator.py")
    assert set(operator.SQL_TEMPLATES) == {"setup", "reviewer", "owner", "cleanup"}
    templates = "\n".join(operator.SQL_TEMPLATES.values())
    assert WORKSPACE_ID in templates and JOB_ID in templates
    assert ":auth_user_id" in templates
    assert "private-real-user-id" not in templates
    assert "on conflict do update" not in templates.lower()
    assert "on conflict do nothing" not in templates.lower()
    assert operator.live_capability_status(
        official_session=None, approved_head=None, final_packet=None
    ) == "WAITING_AUTH_CAPABILITY"
    result = operator.main([])
    assert result == 2


def test_profile_cleanup_is_confined_and_preexisting_profile_is_preserved(tmp_path, monkeypatch):
    pilot = load_script("api_chain_synthetic_pilot.py")
    run_dir = tmp_path / "owned-run"
    profile = run_dir / "profile"
    profile.mkdir(parents=True)
    marker = profile / "owned.txt"
    marker.write_text("owned", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_marker = outside / "keep.txt"
    outside_marker.write_text("keep", encoding="utf-8")

    with pytest.raises(pilot.PilotBlocked, match="PROFILE_BOUNDARY_BLOCKED"):
        pilot.remove_profile(outside, run_dir, tmp_path)
    assert outside_marker.read_text(encoding="utf-8") == "keep"
    assert pilot.remove_profile(profile, run_dir, tmp_path)
    assert not profile.exists()

    preexisting_profile = tmp_path / "profile"
    preexisting_profile.mkdir()
    preexisting_marker = preexisting_profile / "keep.txt"
    preexisting_marker.write_text("owned-before-this-run", encoding="utf-8")
    monkeypatch.setattr(pilot.importlib.metadata, "version", lambda _: "0.13.6")
    monkeypatch.setattr(pilot, "context", lambda *_args, **_kwargs: (HEAD, "42"))
    with pytest.raises(pilot.PilotBlocked, match="PROFILE_PREEXISTS"):
        pilot.supervise(workflow_environment(), tmp_path / "receipt.json", str(outside_marker))
    assert preexisting_marker.read_text(encoding="utf-8") == "owned-before-this-run"


def test_owned_chromium_is_killed_even_after_worker_parent_exits(monkeypatch):
    pilot = load_script("api_chain_synthetic_pilot.py")
    child = Mock()
    child.alive = True
    child.kill.side_effect = lambda: setattr(child, "alive", False)
    parent_identity = {"pid": 42, "created": 1.0}
    owned = {}

    def observe(identity, captured):
        if identity == parent_identity:
            captured[43] = {"pid": 43, "created": 2.0, "name": "chrome"}

    def running(identity):
        return child if identity["pid"] == 43 and child.alive else None

    monkeypatch.setattr(pilot.runtime_helpers, "observe_children", observe)
    monkeypatch.setattr(pilot.runtime_helpers, "running", running)
    monkeypatch.setattr(pilot.runtime_helpers, "zombie_pids", lambda _: [])
    parent_process = Mock(poll=Mock(return_value=0))

    residual, zombies = pilot._stop_owned_processes(parent_identity, owned, parent_process)

    child.kill.assert_called_once()
    assert residual == [] and zombies == []


def test_cleanup_sql_locks_exact_rows_and_rejects_nonterminal_jobs_before_delete():
    import re

    operator = load_script("api_chain_operator.py")
    cleanup = operator.SQL_TEMPLATES["cleanup"].lower()
    first_delete = cleanup.index("delete from public.automation_jobs")
    workspace_delete = cleanup.index("delete from public.workspaces")

    workspace_lock = re.search(
        r"select\s+\*\s+into\s+target_workspace\s+from\s+public\.workspaces"
        r"\s+where\s+id\s*=.*?for\s+update",
        cleanup,
        re.S,
    )
    job_lock = re.search(
        r"select\s+\*\s+into\s+target_job\s+from\s+public\.automation_jobs"
        r"\s+where\s+id\s*=.*?for\s+update",
        cleanup,
        re.S,
    )
    terminal_gate = re.search(
        r"if\s+target_job\.status\s+not\s+in\s*\(\s*'succeeded'\s*,\s*'cancelled'\s*\)"
        r"\s+and\s+not\s*\(\s*target_job\.status\s+in\s*\(\s*'failed'\s*,\s*'partial'\s*\)"
        r"\s+and\s+target_job\.attempt_count\s*>=\s*target_job\.max_attempts\s*\)",
        cleanup,
        re.S,
    )
    active_run_gate = re.search(
        r"from\s+public\.automation_runs\s+run\s+where\s+run\.job_id\s*=\s*target_job\.id"
        r"\s+and\s*\(\s*run\.status\s*=\s*'running'\s+or\s+run\.finished_at\s+is\s+null\s*\)",
        cleanup,
        re.S,
    )

    assert workspace_lock is not None and workspace_lock.start() < first_delete
    assert job_lock is not None and job_lock.start() < first_delete
    assert terminal_gate is not None and terminal_gate.start() < first_delete
    assert active_run_gate is not None and active_run_gate.start() < first_delete
    assert "target_job.workspace_id is distinct from" in cleanup[:first_delete]
    assert "target_job.idempotency_key is distinct from" in cleanup[:first_delete]
    assert "target_job.payload_json is distinct from" in cleanup[:first_delete]
    assert "if target_job.id is not null then" in cleanup[:first_delete]
    assert workspace_delete > first_delete


@pytest.mark.parametrize("cleanup_outcome", ["residual", "zombie", "exception"])
def test_supervise_blocks_and_keeps_profile_when_final_cleanup_is_unconfirmed(
    tmp_path, monkeypatch, cleanup_outcome
):
    from types import SimpleNamespace

    pilot = load_script("api_chain_synthetic_pilot.py")
    receipt_file = tmp_path / "receipt.json"
    preflight = pilot.preflight(
        workflow_environment(),
        receipt_file,
        lambda _token: history_bytes(current_run()),
    )
    assert preflight["status"] == "PREFLIGHT_PASS"

    run_environment = dict(workflow_environment())
    run_environment.pop("GITHUB_TOKEN")
    run_environment["SUPABASE_SECRET_KEY"] = "synthetic-runner-key"
    chromium = tmp_path / "chrome.exe"
    chromium.write_bytes(b"synthetic executable marker")
    profile = tmp_path / "profile"
    cleanup_calls = []

    class FakeProcess:
        pid = 4242
        returncode = 0

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            del timeout
            return self.returncode

        def kill(self):
            raise AssertionError("already exited synthetic worker must not be killed")

    process = FakeProcess()

    def launch_worker(*_args, **_kwargs):
        profile.mkdir()
        (profile / "synthetic-owned.txt").write_text("worker-owned", encoding="utf-8")
        worker_receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        worker_receipt.update(
            status="WORKER_RETURNED",
            cli_outcome={"status": "succeeded", "records_read": 0, "duration_ms": 650000},
        )
        pilot.persist(receipt_file, worker_receipt)
        return process

    def final_cleanup(_parent, _owned, _process):
        cleanup_calls.append(True)
        if cleanup_outcome == "residual":
            return ([{"pid": 4343, "created": 12.0, "name": "chrome"}], [])
        if cleanup_outcome == "zombie":
            return ([], [4343])
        raise RuntimeError("synthetic process cleanup uncertainty")

    monkeypatch.setattr(pilot.importlib.metadata, "version", lambda _name: "0.13.6")
    monkeypatch.setattr(pilot.subprocess, "Popen", launch_worker)
    monkeypatch.setattr(pilot, "_verify_worker", lambda _receipt, _exit: None)
    monkeypatch.setattr(pilot, "_stop_owned_processes", final_cleanup)
    monkeypatch.setitem(
        sys.modules,
        "psutil",
        SimpleNamespace(Process=lambda _pid: SimpleNamespace(create_time=lambda: 1.0)),
    )

    result = pilot.supervise(run_environment, receipt_file, str(chromium))
    persisted = json.loads(receipt_file.read_text(encoding="utf-8"))

    assert cleanup_calls == [True]
    assert result["status"] == "BLOCKED"
    assert persisted["status"] == "BLOCKED"
    assert result == persisted
    assert persisted["error_code"] == "PILOT_CLEANUP_UNCONFIRMED"
    if cleanup_outcome == "residual":
        assert persisted["residual_processes"] == [{"pid": 4343, "created": 12.0, "name": "chrome"}]
    elif cleanup_outcome == "zombie":
        assert persisted["zombie_pids"] == [4343]
    assert profile.exists()
    assert (profile / "synthetic-owned.txt").read_text(encoding="utf-8") == "worker-owned"
