"""A fixed, disabled-until-approved synthetic pilot. Never a Teaching runner."""

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/browser-runner/src"))
from mindx_runner.browser_state import BrowserStateCipher, EncryptedStateEnvelope  # noqa: E402
from mindx_runner.supabase_client import HttpResponse, SupabaseRunnerClient  # noqa: E402

BASE_URL = "https://gnvzjvgfsxfjgldatbwt.supabase.co"
WORKSPACE = "e4741700-beee-4654-943b-cf6e3b7b551b"
WORKSPACE_NAME = "phase2-storage-synthetic-20261005"
VERSION_IDS = [
    "b9329faf-b49b-4f15-b7a0-b5acb0a8fd2b",
    "99c097cd-1722-4a4e-accf-dc79ba0bcc1c",
]
RAW_HASHES = [
    "fa55603b4154c3080f9f1f10f85f991d823b10424315dd626da64f7ca5916750",
    "8d63e3e048ed37e59d8991d6060afdd4df3126750266d4fa0d2b992002ff699c",
]
STATE_HASHES = [
    "8568609ecec55ca7a658b62f26788eda4c61a46cf4abd14872b91d12347b1cf2",
    "e146b710ba8c32c12b81fd8b4a3dd62d4788433bb6d603e4e5ce667776deafe7",
]
PATHS = [f"{WORKSPACE}/teaching/{version}.json" for version in VERSION_IDS]
LIMITS = {
    "github_read": 1,
    "read": 31,
    "upload": 2,
    "download": 2,
    "rpc": 3,
    "delete": 1,
}


class PilotBlocked(Exception):
    pass


def require(condition, code):
    if not condition:
        raise PilotBlocked(code)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_once(method, url, headers, body, *, max_response_bytes=32_768):
    """No redirects/retries; bounded response; auth stays on its original host."""
    require(type(max_response_bytes) is int and max_response_bytes in {32_768, 65_536},
            "PILOT_RESPONSE_LIMIT_BLOCKED")
    request = Request(url, data=body, headers=dict(headers), method=method)
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            raw = response.read(max_response_bytes + 1)
            require(len(raw) <= max_response_bytes, "PILOT_RESPONSE_TOO_LARGE")
            return HttpResponse(response.status, raw)
    except HTTPError as error:
        with error:
            raw = error.read(max_response_bytes + 1)
            require(len(raw) <= max_response_bytes, "PILOT_RESPONSE_TOO_LARGE")
            return HttpResponse(error.code, raw)


def verify_fixture(raw, index):
    require(
        0 < len(raw) <= 1024 and hashlib.sha256(raw).hexdigest() == RAW_HASHES[index],
        "PILOT_FIXTURE_MISMATCH",
    )
    envelope = EncryptedStateEnvelope.from_bytes(raw)
    require(
        envelope.key_version == index + 1
        and envelope.state_hash == STATE_HASHES[index],
        "PILOT_FIXTURE_MISMATCH",
    )
    key = hashlib.sha256(
        f"public-synthetic-storage-fixture-{index + 1}".encode()
    ).digest()
    state = BrowserStateCipher(key, index + 1).decrypt(envelope, site="teaching")
    expected = {
        "cookies": [],
        "origins": [
            {
                "origin": "https://teachingmindx.top",
                "localStorage": [
                    {
                        "name": "phase2-synthetic-fixture",
                        "value": f"public-fixture-{index + 1}",
                    }
                ],
            }
        ],
    }
    require(json.loads(state) == expected, "PILOT_FIXTURE_MISMATCH")


def execute(environment, report, transport=None, *, preflight_only=False):
    receipt = {
        "status": "STARTED",
        "workspace": WORKSPACE,
        "counts": dict.fromkeys(LIMITS, 0),
        "intents": [],
        "checks": [],
    }
    if preflight_only:
        try:
            with report.open("x", encoding="utf-8") as stream:
                json.dump(receipt, stream)
        except FileExistsError:
            return {"status": "FAILED", "error_code": "PILOT_ALREADY_ATTEMPTED"}
    else:
        try:
            receipt = json.loads(report.read_text(encoding="utf-8"))
            require(
                receipt.get("status") == "PREFLIGHT_PASS"
                and receipt.get("workspace") == WORKSPACE
                and receipt.get("head") == environment.get("GITHUB_SHA")
                and receipt.get("run_id") == environment.get("GITHUB_RUN_ID")
                and receipt.get("counts")
                == {**dict.fromkeys(LIMITS, 0), "github_read": 1}
                and receipt.get("checks") == ["FIRST_DISPATCH_CONFIRMED"]
                and receipt.get("intents")
                == [{"kind": "github_read", "ordinal": 1, "outcome": "HTTP_2XX"}],
                "PILOT_PREFLIGHT_REQUIRED",
            )
        except Exception:
            return {"status": "FAILED", "error_code": "PILOT_PREFLIGHT_REQUIRED"}

    def persist():
        with report.open("w", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())

    if not preflight_only:
        receipt["status"] = "STARTED"  # Consume the API phase before any API request.
        persist()

    def send(kind, method, url, headers, body):
        require(receipt["counts"][kind] < LIMITS[kind], "PILOT_BUDGET_EXHAUSTED")
        receipt["counts"][kind] += 1
        intent = {
            "kind": kind,
            "ordinal": receipt["counts"][kind],
            "outcome": "UNKNOWN",
        }
        receipt["intents"].append(intent)
        persist()  # A failed or unknown request consumes its slot before transmission.
        try:
            response = (transport or request_once)(method, url, headers, body)
        except Exception as error:
            raise PilotBlocked("PILOT_REQUEST_FAILED") from error
        intent["outcome"] = (
            "HTTP_2XX" if 200 <= response.status < 300 else "HTTP_NON_SUCCESS"
        )
        persist()
        require(200 <= response.status < 300, "PILOT_REQUEST_REJECTED")
        return response

    try:
        require(
            environment.get("GITHUB_REPOSITORY") == "Banhtalon/mindx-review-bot"
            and environment.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and environment.get("GITHUB_RUN_ATTEMPT") == "1",
            "PILOT_CONTEXT_INVALID",
        )
        sha = environment.get("GITHUB_SHA", "")
        run_id = environment.get("GITHUB_RUN_ID", "")
        require(
            re.fullmatch(r"[a-f0-9]{40}", sha)
            and environment.get("MINDX_STORAGE_PILOT_APPROVAL_SHA") == sha
            and run_id.isdigit()
            and int(run_id) > 0,
            "PILOT_APPROVAL_REQUIRED",
        )
        require(
            environment.get("SUPABASE_URL", BASE_URL) == BASE_URL,
            "PILOT_CONTEXT_INVALID",
        )
        fixtures = [
            (ROOT / "scripts/fixtures/storage-pilot" / f"{version}.json").read_bytes()
            for version in VERSION_IDS
        ]
        for index, raw in enumerate(fixtures):
            verify_fixture(raw, index)

        if preflight_only:
            require(
                "SUPABASE_SECRET_KEY" not in environment
                and environment.get("GITHUB_TOKEN"),
                "PILOT_PREFLIGHT_CREDENTIAL_SCOPE",
            )
            history_url = "https://api.github.com/repos/Banhtalon/mindx-review-bot/actions/workflows/storage-synthetic-pilot.yml/runs?event=workflow_dispatch&per_page=100"
            history_response = send(
                "github_read",
                "GET",
                history_url,
                {
                    "Authorization": "Bearer " + environment["GITHUB_TOKEN"],
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                None,
            )
            history = json.loads(history_response.body)
            runs = history["workflow_runs"]
            require(
                isinstance(runs, list)
                and 0 < history["total_count"] <= 100
                and history["total_count"] == len(runs)
                and sum(run["id"] == int(run_id) for run in runs) == 1
                and all(
                    isinstance(run["id"], int) and run["id"] >= int(run_id)
                    for run in runs
                ),
                "PILOT_PRIOR_OR_AMBIGUOUS_DISPATCH",
            )
            receipt.update(status="PREFLIGHT_PASS", head=sha, run_id=run_id)
            receipt["checks"].append("FIRST_DISPATCH_CONFIRMED")
            persist()
            return receipt
        require(
            environment.get("SUPABASE_URL") == BASE_URL
            and environment.get("SUPABASE_SECRET_KEY"),
            "PILOT_CONTEXT_INVALID",
        )

        kind = "read"
        client = SupabaseRunnerClient(
            BASE_URL,
            environment["SUPABASE_SECRET_KEY"],
            transport=lambda method, url, headers, body: send(
                kind, method, url, headers, body
            ),
        )

        def data(method, path, body=None):
            response = client._request(
                method,
                path,
                None if body is None else json.dumps(body).encode(),
                content_type="application/json" if body is not None else None,
            )
            return json.loads(response.body)

        def inventory(expected):
            parent = data(
                "POST",
                "/storage/v1/object/list/browser-state",
                {"prefix": WORKSPACE, "limit": 3, "offset": 0},
            )
            children = data(
                "POST",
                "/storage/v1/object/list/browser-state",
                {"prefix": WORKSPACE + "/teaching", "limit": 3, "offset": 0},
            )
            require(
                isinstance(parent, list) and isinstance(children, list),
                "PILOT_OBJECT_SCOPE_MISMATCH",
            )
            require(
                len(parent) == (1 if expected else 0)
                and all(
                    item.get("id") is None and item.get("name") == "teaching"
                    for item in parent
                ),
                "PILOT_OBJECT_SCOPE_MISMATCH",
            )
            actual = {WORKSPACE + "/teaching/" + item["name"] for item in children}
            require(
                len(children) == len(expected)
                and actual == set(expected)
                and all(
                    item.get("id") is not None
                    and 0 < item.get("metadata", {}).get("size", 0) <= 1024
                    for item in children
                ),
                "PILOT_OBJECT_SCOPE_MISMATCH",
            )

        def guard(statuses, expected_objects):
            workspaces = data(
                "GET", f"/rest/v1/workspaces?id=eq.{WORKSPACE}&select=id,name&limit=2"
            )
            require(
                workspaces == [{"id": WORKSPACE, "name": WORKSPACE_NAME}],
                "PILOT_WORKSPACE_MISMATCH",
            )
            for table in ("workspace_members", "automation_jobs", "automation_runs"):
                require(
                    data(
                        "GET",
                        f"/rest/v1/{table}?workspace_id=eq.{WORKSPACE}&select=workspace_id&limit=1",
                    )
                    == [],
                    "PILOT_WORKSPACE_NOT_ISOLATED",
                )
            versions = data(
                "GET",
                f"/rest/v1/browser_state_versions?workspace_id=eq.{WORKSPACE}&select=id,workspace_id,site,object_path,key_version,state_hash,status&limit=3",
            )
            expected_versions = [
                {
                    "id": VERSION_IDS[index],
                    "workspace_id": WORKSPACE,
                    "site": "teaching",
                    "object_path": "browser-state/" + PATHS[index],
                    "key_version": index + 1,
                    "state_hash": STATE_HASHES[index],
                    "status": status,
                }
                for index, status in enumerate(statuses)
            ]
            require(
                isinstance(versions, list)
                and sorted(versions, key=lambda v: v["id"])
                == sorted(expected_versions, key=lambda v: v["id"]),
                "PILOT_VERSION_SCOPE_MISMATCH",
            )
            inventory(expected_objects)
            receipt["checks"].append("EXACT_SCOPE_" + str(len(statuses)))
            persist()

        bucket = data("GET", "/storage/v1/bucket/browser-state")
        require(
            bucket.get("id") == "browser-state" and bucket.get("public") is False,
            "PILOT_BUCKET_NOT_PRIVATE",
        )
        guard([], [])
        for index, raw in enumerate(fixtures):
            kind = "upload"
            client.object_store.put("browser-state/" + PATHS[index], raw)
            kind = "download"
            downloaded = client.object_store.get("browser-state/" + PATHS[index])
            verify_fixture(downloaded, index)
            receipt["checks"].append("DOWNLOADED_CRYPTO_" + str(index + 1))
            kind = "rpc"
            activated = client._rpc(
                "activate_browser_state_version",
                {
                    "target_workspace_id": WORKSPACE,
                    "target_site": "teaching",
                    "target_version_id": VERSION_IDS[index],
                    "target_object_path": "browser-state/" + PATHS[index],
                    "target_key_version": index + 1,
                    "target_state_hash": STATE_HASHES[index],
                },
            )
            require(
                activated
                == [
                    {
                        "version_id": VERSION_IDS[index],
                        "object_path": "browser-state/" + PATHS[index],
                        "status": "active",
                    }
                ],
                "PILOT_ACTIVATION_UNPROVEN",
            )
            kind = "read"
            guard(
                ["active"] if index == 0 else ["revoked", "active"], PATHS[: index + 1]
            )

        kind = "rpc"
        reset = client._rpc(
            "reset_browser_state",
            {"target_workspace_id": WORKSPACE, "target_site": "teaching"},
        )
        require(
            reset == [{"object_path": "browser-state/" + PATHS[1]}],
            "PILOT_RESET_UNPROVEN",
        )
        kind = "read"
        guard(["revoked", "revoked"], PATHS)
        kind = "delete"
        data("DELETE", "/storage/v1/object/browser-state", {"prefixes": PATHS})
        kind = "read"
        inventory([])
        receipt["checks"].append("STORAGE_OBJECTS_ZERO")
        receipt["status"] = "PASS"
    except Exception as error:
        receipt["status"] = "FAILED"
        receipt["error_code"] = (
            str(error) if isinstance(error, PilotBlocked) else "PILOT_VALIDATION_FAILED"
        )
    persist()
    return receipt


if __name__ == "__main__":
    try:
        require(sys.argv[1:] in ([], ["--preflight"]), "PILOT_CONTEXT_INVALID")
        result = execute(
            os.environ,
            Path("storage-pilot-receipt.json"),
            preflight_only=sys.argv[1:] == ["--preflight"],
        )
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in ("status", "counts", "error_code")
                    if key in result
                }
            )
        )
        sys.exit(0 if result["status"] in {"PASS", "PREFLIGHT_PASS"} else 1)
    except Exception:
        print("PILOT_RECEIPT_UNAVAILABLE")
        sys.exit(1)
