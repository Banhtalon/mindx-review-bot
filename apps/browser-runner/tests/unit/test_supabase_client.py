import json
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from mindx_runner.browser_state import BrowserStateCipher
from mindx_runner.supabase_client import (
    ClaimedRun,
    HttpResponse,
    ReviewInputSnapshot,
    SupabaseClientError,
    SupabaseRunnerClient,
)

BASE_URL = "https://example.supabase.co"
SECRET = "server-secret"
JOB_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
WORKSPACE_ID = "00000000-0000-4000-8000-000000000003"
SESSION_ID = "00000000-0000-4000-8000-000000000004"
STUDENT_ID = "00000000-0000-4000-8000-000000000005"
RUNNER_ID = "runner-test-01"
OBJECT_PATH = f"browser-state/{WORKSPACE_ID}/lms/{RUN_ID}.json"
TEACHING_OBJECT_PATH = f"browser-state/{WORKSPACE_ID}/teaching/{RUN_ID}.json"
TEACHING_STATE = b'{"cookies":[],"origins":[{"origin":"https://teachingmindx.top","localStorage":[]}]}'


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


@pytest.mark.parametrize("error_code", ["BROWSER_NAVIGATION_FAILED", "BROWSER_STARTUP_FAILED"])
def test_finish_job_run_accepts_safe_browser_lifecycle_errors(error_code: str) -> None:
    transport = FakeTransport([response([{"status": "failed"}])])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    client.finish_job_run(
        RUN_ID,
        RUNNER_ID,
        "failed",
        records_read=0,
        error_code=error_code,
    )

    assert json.loads(transport.requests[0][3] or b"")["target_error_code"] == error_code


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


@pytest.mark.parametrize(
    ("records_read", "duration_ms"),
    [(1.5, 0), ("3", 0), (2_147_483_648, 0), (0, 1.5), (0, "3")],
)
def test_finish_rejects_non_integer_or_out_of_range_metrics(
    records_read: object,
    duration_ms: object,
) -> None:
    transport = FakeTransport([])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.finish_job_run(
            RUN_ID,
            RUNNER_ID,
            "succeeded",
            records_read=records_read,  # type: ignore[arg-type]
            error_code=None,
            duration_ms=duration_ms,  # type: ignore[arg-type]
        )

    assert error.value.code == "RUNNER_RESULT_INVALID"
    assert transport.requests == []


def test_update_review_input_maps_updated_rpc_snapshot() -> None:
    transport = FakeTransport(
        [
            response(
                [
                    {
                        "status": "updated",
                        "workspace_id": WORKSPACE_ID,
                        "session_id": SESSION_ID,
                        "student_id": STUDENT_ID,
                        "attendance": "present",
                        "learning_level": "developing",
                        "note_draft": "Good progress",
                        "revision": 3,
                    }
                ]
            )
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    snapshot = client.update_review_input(
        WORKSPACE_ID,
        SESSION_ID,
        STUDENT_ID,
        attendance="present",
        learning_level="developing",
        note_draft="Good progress",
        expected_revision=2,
    )

    assert snapshot == ReviewInputSnapshot(
        workspace_id=WORKSPACE_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        attendance="present",
        learning_level="developing",
        note_draft="Good progress",
        revision=3,
    )
    _, url, _, body = transport.requests[0]
    assert url == f"{BASE_URL}/rest/v1/rpc/update_review_input_if_revision_matches"
    assert json.loads(body or b"") == {
        "target_workspace_id": WORKSPACE_ID,
        "target_session_id": SESSION_ID,
        "target_student_id": STUDENT_ID,
        "target_attendance": "present",
        "target_learning_level": "developing",
        "target_note_draft": "Good progress",
        "target_expected_revision": 2,
    }


def test_update_review_input_maps_stale_revision_to_conflict() -> None:
    transport = FakeTransport(
        [
            response(
                [
                    {
                        "status": "conflict",
                        "workspace_id": WORKSPACE_ID,
                        "session_id": SESSION_ID,
                        "student_id": STUDENT_ID,
                        "attendance": "absent",
                        "learning_level": "strong",
                        "note_draft": "Newer draft",
                        "revision": 4,
                    }
                ]
            )
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.update_review_input(
            WORKSPACE_ID,
            SESSION_ID,
            STUDENT_ID,
            attendance="present",
            learning_level="developing",
            note_draft="Stale draft",
            expected_revision=2,
        )

    assert error.value.code == "REVIEW_INPUT_REVISION_CONFLICT"


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


def test_persist_browser_state_encrypts_before_upload_and_activates_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mindx_runner.supabase_client.uuid4", lambda: RUN_ID)
    transport = FakeTransport(
        [
            response({"Key": f"{WORKSPACE_ID}/teaching/{RUN_ID}.json"}),
            response(
                [
                    {
                        "version_id": RUN_ID,
                        "object_path": TEACHING_OBJECT_PATH,
                        "status": "active",
                    }
                ]
            ),
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    version = client.persist_browser_state(
        WORKSPACE_ID,
        "teaching",
        TEACHING_STATE,
        BrowserStateCipher(b"k" * 32, key_version=3),
    )

    assert version.workspace_id == WORKSPACE_ID
    assert version.site == "teaching"
    assert version.key_version == 3
    assert version.object_path.startswith(f"browser-state/{WORKSPACE_ID}/teaching/")
    assert version.object_path.endswith(".json")
    uploaded = transport.requests[0][3]
    assert uploaded is not None
    assert b"teachingmindx.top" not in uploaded
    assert b"cookies" not in uploaded
    activation = json.loads(transport.requests[1][3] or b"")
    assert activation["target_workspace_id"] == WORKSPACE_ID
    assert activation["target_site"] == "teaching"
    assert activation["target_version_id"] == version.version_id
    assert activation["target_object_path"] == version.object_path


def test_activate_browser_state_rejects_mismatched_metadata() -> None:
    transport = FakeTransport(
        [
            response(
                [
                    {
                        "version_id": RUN_ID,
                        "object_path": OBJECT_PATH,
                        "status": "active",
                    }
                ]
            )
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.activate_browser_state_version(
            WORKSPACE_ID,
            "teaching",
            RUN_ID,
            TEACHING_OBJECT_PATH,
            1,
            "a" * 64,
        )

    assert error.value.code == "SUPABASE_UNAVAILABLE"


def test_persist_browser_state_keeps_object_if_activation_outcome_is_unknown() -> None:
    transport = FakeTransport(
        [
            response({"Key": f"{WORKSPACE_ID}/teaching/{RUN_ID}.json"}),
            HttpResponse(status=500, body=b"redacted"),
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.persist_browser_state(
            WORKSPACE_ID,
            "teaching",
            TEACHING_STATE,
            BrowserStateCipher(b"k" * 32, key_version=1),
        )

    assert error.value.code == "SUPABASE_UNAVAILABLE"
    assert len(transport.requests) == 2
    assert transport.requests[0][0] == "POST"


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


def test_load_active_browser_state_returns_encrypted_object_bytes() -> None:
    encrypted = b'{"ciphertext":"redacted"}'
    transport = FakeTransport(
        [
            response([{"object_path": OBJECT_PATH}]),
            HttpResponse(status=200, body=encrypted),
        ]
    )
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    assert client.load_active_browser_state(WORKSPACE_ID, "lms") == encrypted
    assert transport.requests[0][0] == "GET"
    assert (
        transport.requests[0][1]
        == f"{BASE_URL}/rest/v1/browser_state_versions?workspace_id=eq.{WORKSPACE_ID}"
        f"&site=eq.lms&status=eq.active&select=object_path&limit=1"
    )
    assert transport.requests[1][0] == "GET"


def test_load_active_browser_state_returns_none_without_active_version() -> None:
    transport = FakeTransport([response([])])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    assert client.load_active_browser_state(WORKSPACE_ID, "teaching") is None


def test_load_active_browser_state_rejects_cross_workspace_metadata() -> None:
    other_path = f"browser-state/{RUN_ID}/lms/{RUN_ID}.json"
    transport = FakeTransport([response([{"object_path": other_path}])])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.load_active_browser_state(WORKSPACE_ID, "lms")

    assert error.value.code == "STORAGE_PATH_INVALID"
    assert len(transport.requests) == 1


def test_load_active_browser_state_rejects_unknown_site_before_network_call() -> None:
    transport = FakeTransport([])
    client = SupabaseRunnerClient(BASE_URL, SECRET, transport=transport)

    with pytest.raises(SupabaseClientError) as error:
        client.load_active_browser_state(WORKSPACE_ID, "other")

    assert error.value.code == "RUNNER_RESULT_INVALID"
    assert transport.requests == []
