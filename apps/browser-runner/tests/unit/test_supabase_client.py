import json
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from mindx_runner.supabase_client import (
    ClaimedRun,
    HttpResponse,
    SupabaseClientError,
    SupabaseRunnerClient,
)

BASE_URL = "https://example.supabase.co"
SECRET = "server-secret"
JOB_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
WORKSPACE_ID = "00000000-0000-4000-8000-000000000003"
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

    claimed = client.claim_job_run(JOB_ID)

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
    assert json.loads(body or b"") == {"target_job_id": JOB_ID}
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert headers["apikey"] == SECRET


def test_claim_rejects_invalid_response_without_leaking_body() -> None:
    transport = FakeTransport([HttpResponse(status=500, body=b"password=hidden")])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.claim_job_run(JOB_ID)

    assert error.value.code == "SUPABASE_UNAVAILABLE"
    assert "hidden" not in str(error.value)


def test_finish_job_run_sends_allowlisted_terminal_status() -> None:
    transport = FakeTransport([response([{"status": "succeeded"}])])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    client.finish_job_run(RUN_ID, "succeeded", records_read=3, error_code=None)

    _, url, _, body = transport.requests[0]
    assert url == f"{BASE_URL}/rest/v1/rpc/finish_automation_job_run"
    assert json.loads(body or b"") == {
        "target_run_id": RUN_ID,
        "target_status": "succeeded",
        "target_records_read": 3,
        "target_error_code": None,
    }


def test_finish_rejects_unknown_error_code_before_network_call() -> None:
    transport = FakeTransport([])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.finish_job_run(RUN_ID, "failed", records_read=0, error_code="PII_VALUE")

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
