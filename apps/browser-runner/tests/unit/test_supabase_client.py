import json
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from mindx_runner.supabase_client import (
    BrowserStateRecord,
    ClaimedRun,
    EnqueuedProbeJob,
    HttpResponse,
    SupabaseClientError,
    SupabaseRunnerClient,
)

BASE_URL = "https://example.supabase.co"
SECRET = "server-secret"
JOB_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
WORKSPACE_ID = "00000000-0000-4000-8000-000000000003"
RUNNER_ID = "runner-test-01"
OBJECT_PATH = f"browser-state/{WORKSPACE_ID}/lms/{RUN_ID}.json"


@dataclass
class FakeTransport:
    responses: list[HttpResponse]

    def __post_init__(self) -> None:
        self.requests: list[tuple[str, str, Mapping[str, str], bytes | None]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> HttpResponse:
        self.requests.append((method, url, headers, body))
        return self.responses.pop(0)

    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> HttpResponse:
        return self.request(method, url, headers, body)


def response(value: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status=status, body=json.dumps(value).encode("utf-8"))


def test_claim_job_run_posts_only_safe_job_id_and_parses_claim() -> None:
    transport = FakeTransport(
        [
            response(
                [
                    {
                        "claimed": True,
                        "run_id": RUN_ID,
                        "job_id": JOB_ID,
                        "workspace_id": WORKSPACE_ID,
                        "job_type": "read_lms_pending",
                        "payload_json": {},
                        "attempt": 1,
                    }
                ]
            )
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    claimed = client.claim_job_run(JOB_ID, RUNNER_ID)

    assert claimed == ClaimedRun(
        claimed=True,
        run_id=RUN_ID,
        job_id=JOB_ID,
        workspace_id=WORKSPACE_ID,
        job_type="read_lms_pending",
        payload={},
        attempt=1,
    )
    method, url, headers, body = transport.requests[0]
    assert method == "POST"
    assert url == f"{BASE_URL}/rest/v1/rpc/claim_automation_job_run"
    assert json.loads(body or b"") == {
        "target_job_id": JOB_ID,
        "target_runner_id": RUNNER_ID,
    }
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert headers["apikey"] == SECRET


def test_claim_rejects_invalid_response_without_leaking_body() -> None:
    transport = FakeTransport([HttpResponse(status=500, body=b"password=hidden")])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.claim_job_run(JOB_ID, RUNNER_ID)

    assert error.value.code == "SUPABASE_UNAVAILABLE"
    assert "hidden" not in str(error.value)


def test_claim_rejects_an_out_of_contract_attempt_count() -> None:
    transport = FakeTransport(
        [
            response(
                [
                    {
                        "claimed": True,
                        "run_id": RUN_ID,
                        "job_id": JOB_ID,
                        "workspace_id": WORKSPACE_ID,
                        "job_type": "read_lms_pending",
                        "payload_json": {},
                        "attempt": 4,
                    }
                ]
            )
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.claim_job_run(JOB_ID, RUNNER_ID)

    assert error.value.code == "SUPABASE_UNAVAILABLE"


def test_finish_job_run_sends_allowlisted_terminal_status() -> None:
    transport = FakeTransport([response([{"status": "succeeded"}])])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    client.finish_job_run(
        RUN_ID,
        RUNNER_ID,
        "succeeded",
        records_read=3,
        error_code=None,
        duration_ms=123,
    )

    _, url, _, body = transport.requests[0]
    assert url == f"{BASE_URL}/rest/v1/rpc/finish_automation_job_run"
    assert json.loads(body or b"") == {
        "target_run_id": RUN_ID,
        "target_runner_id": RUNNER_ID,
        "target_status": "succeeded",
        "target_records_read": 3,
        "target_error_code": None,
        "target_duration_ms": 123,
    }


def test_heartbeat_job_sends_runner_owned_lease_refresh() -> None:
    transport = FakeTransport([response([{"job_id": JOB_ID, "runner_id": RUNNER_ID}])])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    client.heartbeat_job(JOB_ID, RUNNER_ID)

    _, url, _, body = transport.requests[0]
    assert url == f"{BASE_URL}/rest/v1/rpc/heartbeat_automation_job"
    assert json.loads(body or b"") == {
        "target_job_id": JOB_ID,
        "target_runner_id": RUNNER_ID,
    }


def test_finish_surfaces_safe_server_rejection_without_response_body() -> None:
    transport = FakeTransport([HttpResponse(status=403, body=b"runner=other-secret")])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.finish_job_run(
            RUN_ID,
            "runner-other",
            "succeeded",
            records_read=0,
            error_code=None,
        )

    assert error.value.code == "SUPABASE_UNAVAILABLE"
    assert "other-secret" not in str(error.value)


def test_finish_rejects_unknown_error_code_before_network_call() -> None:
    transport = FakeTransport([])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.finish_job_run(
            RUN_ID,
            RUNNER_ID,
            "failed",
            records_read=0,
            error_code="PII_VALUE",
        )

    assert error.value.code == "RUNNER_RESULT_INVALID"
    assert transport.requests == []


def test_storage_object_store_uses_private_bucket_rest_endpoints() -> None:
    transport = FakeTransport(
        [
            response({"Key": OBJECT_PATH}, status=200),
            HttpResponse(status=200, body=b"encrypted-envelope"),
            response([], status=200),
        ]
    )
    store = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport).object_store

    store.put(OBJECT_PATH, b"encrypted-envelope")
    assert store.get(OBJECT_PATH) == b"encrypted-envelope"
    store.delete(OBJECT_PATH)

    assert transport.requests[0][0] == "POST"
    assert transport.requests[0][1].endswith(
        f"/storage/v1/object/browser-state/{WORKSPACE_ID}/lms/{RUN_ID}.json"
    )
    assert transport.requests[1][0] == "GET"
    assert transport.requests[2][0] == "DELETE"
    assert json.loads(transport.requests[2][3] or b"") == {
        "prefixes": [f"{WORKSPACE_ID}/lms/{RUN_ID}.json"]
    }


def test_storage_object_store_rejects_path_traversal() -> None:
    transport = FakeTransport([])
    store = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport).object_store

    with pytest.raises(SupabaseClientError) as error:
        store.get("../credentials.json")

    assert error.value.code == "STORAGE_PATH_INVALID"
    assert transport.requests == []


def test_storage_object_store_rejects_unscoped_state_path() -> None:
    transport = FakeTransport([])
    store = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport).object_store

    with pytest.raises(SupabaseClientError) as error:
        store.get("browser-state/other-folder/state.json")

    assert error.value.code == "STORAGE_PATH_INVALID"
    assert transport.requests == []


def test_get_active_browser_state_requires_one_strictly_valid_row() -> None:
    transport = FakeTransport(
        [
            response(
                [
                    {
                        "id": RUN_ID,
                        "workspace_id": WORKSPACE_ID,
                        "site": "lms",
                        "object_path": OBJECT_PATH,
                        "key_version": 1,
                        "state_hash": "a" * 64,
                        "status": "active",
                    }
                ]
            )
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    record = client.get_active_browser_state(WORKSPACE_ID, "lms")

    assert record == BrowserStateRecord(
        version_id=RUN_ID,
        workspace_id=WORKSPACE_ID,
        site="lms",
        object_path=OBJECT_PATH,
        key_version=1,
        state_hash="a" * 64,
        status="active",
    )
    assert transport.requests[0][0] == "GET"
    assert "browser_state_versions?" in transport.requests[0][1]
    assert "status=eq.active" in transport.requests[0][1]
    assert "limit=2" in transport.requests[0][1]


def test_get_active_browser_state_rejects_duplicate_rows() -> None:
    row = {
        "id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "site": "lms",
        "object_path": OBJECT_PATH,
        "key_version": 1,
        "state_hash": "a" * 64,
        "status": "active",
    }
    transport = FakeTransport([response([row, row])])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.get_active_browser_state(WORKSPACE_ID, "lms")

    assert error.value.code == "SUPABASE_UNAVAILABLE"


def test_delete_probe_rows_uses_exact_validated_filters() -> None:
    transport = FakeTransport([response([]), response([])])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    client.delete_probe_rows(RUN_ID, "phase2-probe:00000000-0000-4000-8000-000000000002")

    assert transport.requests[0][0] == "DELETE"
    assert transport.requests[0][1].endswith(f"/rest/v1/browser_state_versions?id=eq.{RUN_ID}")
    assert transport.requests[1][0] == "DELETE"
    assert "idempotency_key=eq.phase2-probe%3A" in transport.requests[1][1]


def test_delete_probe_rows_rejects_a_broad_filter_before_network() -> None:
    transport = FakeTransport([])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.delete_probe_rows(RUN_ID, "phase2-probe:*")

    assert error.value.code == "RUNNER_RESULT_INVALID"
    assert transport.requests == []


def test_enqueue_probe_job_uses_existing_internal_rpc_and_empty_payload() -> None:
    transport = FakeTransport(
        [
            response(
                [
                    {
                        "job_id": JOB_ID,
                        "workspace_id": WORKSPACE_ID,
                        "job_type": "read_lms_pending",
                        "status": "queued",
                        "idempotency_key": f"phase2-probe:{RUN_ID}",
                        "payload_json": {},
                        "requested_by": RUN_ID,
                        "created": True,
                    }
                ]
            )
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    result = client.enqueue_probe_job(WORKSPACE_ID, RUN_ID, RUN_ID)

    assert result == EnqueuedProbeJob(
        JOB_ID,
        WORKSPACE_ID,
        "read_lms_pending",
        "queued",
        f"phase2-probe:{RUN_ID}",
        True,
    )
    assert transport.requests[0][1].endswith("/rest/v1/rpc/enqueue_automation_job")
    assert json.loads(transport.requests[0][3] or b"") == {
        "target_workspace_id": WORKSPACE_ID,
        "target_type": "read_lms_pending",
        "target_idempotency_key": f"phase2-probe:{RUN_ID}",
        "target_payload": {},
        "target_requested_by": RUN_ID,
    }


def test_expire_probe_lease_patches_only_the_exact_job() -> None:
    transport = FakeTransport([HttpResponse(status=204, body=b"")])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    client.expire_probe_lease(JOB_ID)

    method, url, _, body = transport.requests[0]
    assert method == "PATCH"
    assert url.endswith(f"/rest/v1/automation_jobs?id=eq.{JOB_ID}")
    assert json.loads(body or b"") == {
        "heartbeat_at": "2000-01-01T00:00:00Z",
        "lease_expires_at": "2000-01-01T00:00:00Z",
    }


def test_distinct_authorization_token_never_appears_in_repr() -> None:
    client = SupabaseRunnerClient(
        BASE_URL,
        "public-anon-key",
        authorization_token="synthetic-user-jwt",
    )

    assert "synthetic-user-jwt" not in repr(client)
    assert "public-anon-key" not in repr(client)


def test_authenticated_role_probe_first_validates_a_real_user_session() -> None:
    transport = FakeTransport([response({"id": RUN_ID})])
    client = SupabaseRunnerClient(
        BASE_URL,
        "public-anon-key",
        authorization_token="synthetic-user-jwt",
        transport=transport,
    )

    assert client.verify_authenticated_identity() == RUN_ID
    method, url, headers, body = transport.requests[0]
    assert method == "GET"
    assert url.endswith("/auth/v1/user")
    assert headers["apikey"] == "public-anon-key"
    assert headers["Authorization"] == "Bearer synthetic-user-jwt"
    assert body is None
