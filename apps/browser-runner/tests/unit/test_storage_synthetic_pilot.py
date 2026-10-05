"""All transports and credentials here are synthetic; no external requests."""

import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from mindx_runner.supabase_client import HttpResponse

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    "storage_synthetic_pilot", ROOT / "scripts/storage_synthetic_pilot.py"
)
assert SPEC is not None and SPEC.loader is not None
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def environment():
    return {
        "GITHUB_REPOSITORY": "Banhtalon/mindx-review-bot",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ID": "10",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "a" * 40,
        "MINDX_STORAGE_PILOT_APPROVAL_SHA": "a" * 40,
        "GITHUB_TOKEN": "synthetic-github-credential",
        "SUPABASE_URL": "https://gnvzjvgfsxfjgldatbwt.supabase.co",
        "SUPABASE_SECRET_KEY": "synthetic-supabase-credential",
    }


def run_pilot(env, report, transport):
    preflight_env = {key: value for key, value in env.items() if key != "SUPABASE_SECRET_KEY"}
    result = pilot.execute(preflight_env, report, transport, preflight_only=True)
    if result["status"] != "PREFLIGHT_PASS":
        return result
    api_env = {key: value for key, value in env.items() if key != "GITHUB_TOKEN"}
    return pilot.execute(api_env, report, transport)


class SyntheticServer:
    def __init__(self):
        self.calls = []
        self.objects = {}
        self.versions = []
        self.members = []
        self.history = {"total_count": 1, "workflow_runs": [{"id": 10}]}
        self.foreign_object = False
        self.corrupt_download = False
        self.bad_version = False
        self.fail_on = None
        self.failed_calls = []
        self.rpc_names = []

    def __call__(self, method, url, headers, body):
        del headers  # Never retain or print even synthetic auth headers.
        self.calls.append((method, url))
        targeted = self.fail_on and self.fail_on in url and method != "GET"
        if self.fail_on == "/storage/v1/object/browser-state":
            targeted = method == "DELETE" and url.endswith(self.fail_on)
        if targeted:
            self.failed_calls.append((method, url))
            raise OSError("untrusted-private-error-text")
        if url.startswith("https://api.github.com/"):
            return HttpResponse(200, json.dumps(self.history).encode())
        route = url.removeprefix(environment()["SUPABASE_URL"])
        payload = (
            json.loads(body)
            if body and not route.startswith("/storage/v1/object/browser-state/")
            else None
        )
        if route == "/storage/v1/bucket/browser-state":
            data = {"id": "browser-state", "public": False}
        elif route.startswith("/rest/v1/workspaces?"):
            data = [{"id": pilot.WORKSPACE, "name": pilot.WORKSPACE_NAME}]
        elif route.startswith("/rest/v1/workspace_members?"):
            data = self.members
        elif route.startswith(("/rest/v1/automation_jobs?", "/rest/v1/automation_runs?")):
            data = []
        elif route.startswith("/rest/v1/browser_state_versions?"):
            data = self.versions.copy()
            if self.bad_version:
                data.append({"id": "foreign-version"})
        elif route == "/storage/v1/object/list/browser-state":
            if payload["prefix"] == pilot.WORKSPACE:
                data = (
                    [{"id": None, "name": "teaching"}]
                    if self.objects or self.foreign_object
                    else []
                )
            else:
                data = [
                    {"id": name, "name": name.rsplit("/", 1)[-1], "metadata": {"size": len(raw)}}
                    for name, raw in self.objects.items()
                ]
                if self.foreign_object:
                    data.append(
                        {
                            "id": "foreign",
                            "name": ".emptyFolderPlaceholder",
                            "metadata": {"size": 0},
                        }
                    )
        elif route.startswith("/storage/v1/object/browser-state/"):
            name = route.removeprefix("/storage/v1/object/browser-state/")
            if method == "POST":
                assert name not in self.objects, "No overwrite permitted"
                self.objects[name] = body
                data = {"Key": "browser-state/" + name}
            else:
                raw = self.objects[name]
                return HttpResponse(200, raw + b"corrupt" if self.corrupt_download else raw)
        elif route.startswith("/rest/v1/rpc/"):
            name = route.rsplit("/", 1)[-1]
            self.rpc_names.append(name)
            if name == "activate_browser_state_version":
                for version in self.versions:
                    version["status"] = "revoked"
                version = {
                    "id": payload["target_version_id"],
                    "workspace_id": pilot.WORKSPACE,
                    "site": "teaching",
                    "object_path": payload["target_object_path"],
                    "key_version": payload["target_key_version"],
                    "state_hash": payload["target_state_hash"],
                    "status": "active",
                }
                self.versions.append(version)
                data = [
                    {
                        "version_id": version["id"],
                        "object_path": version["object_path"],
                        "status": "active",
                    }
                ]
            else:
                data = [
                    {"object_path": v["object_path"]}
                    for v in self.versions
                    if v["status"] == "active"
                ]
                for version in self.versions:
                    version["status"] = "revoked"
        elif route == "/storage/v1/object/browser-state" and method == "DELETE":
            assert set(payload["prefixes"]) == set(self.objects)
            data = [{"name": name} for name in payload["prefixes"]]
            self.objects.clear()
        else:
            raise AssertionError("Unexpected request route")
        return HttpResponse(200, json.dumps(data).encode())


def test_storage_synthetic_exact_lifecycle(tmp_path):
    server = SyntheticServer()
    result = run_pilot(environment(), tmp_path / "receipt.json", server)
    assert result["status"] == "PASS"
    assert result["counts"] == {
        "github_read": 1,
        "read": 31,
        "upload": 2,
        "download": 2,
        "rpc": 3,
        "delete": 1,
    }
    assert len(server.calls) == 40
    assert not server.objects and [v["status"] for v in server.versions] == ["revoked", "revoked"]
    assert server.rpc_names == [
        "activate_browser_state_version",
        "activate_browser_state_version",
        "reset_browser_state",
    ]
    assert all("teachingmindx" not in url for _, url in server.calls)
    receipt = (tmp_path / "receipt.json").read_text()
    assert "synthetic-supabase-credential" not in receipt
    assert "ciphertext" not in receipt and "untrusted-private-error-text" not in receipt


def test_storage_synthetic_preflight_rejects_supabase_key(tmp_path):
    server = SyntheticServer()
    result = pilot.execute(environment(), tmp_path / "receipt.json", server, preflight_only=True)
    assert result["error_code"] == "PILOT_PREFLIGHT_CREDENTIAL_SCOPE"
    assert not server.calls


def test_storage_synthetic_separate_phases_and_api_replay(tmp_path):
    server = SyntheticServer()
    path = tmp_path / "receipt.json"
    env = environment()
    preflight_env = {key: value for key, value in env.items() if not key.startswith("SUPABASE_")}
    result = pilot.execute(preflight_env, path, server, preflight_only=True)
    assert result["status"] == "PREFLIGHT_PASS" and len(server.calls) == 1
    assert server.calls[0][1].startswith("https://api.github.com/")
    api_env = {key: value for key, value in env.items() if key != "GITHUB_TOKEN"}
    assert pilot.execute(api_env, path, server)["status"] == "PASS"
    before, count = path.read_bytes(), len(server.calls)
    assert pilot.execute(api_env, path, server)["error_code"] == "PILOT_PREFLIGHT_REQUIRED"
    assert path.read_bytes() == before and len(server.calls) == count


@pytest.mark.parametrize("problem", ["missing", "head", "run_id", "counts", "intents"])
def test_storage_synthetic_api_requires_bound_preflight(tmp_path, problem):
    server = SyntheticServer()
    path = tmp_path / "receipt.json"
    env = environment()
    if problem != "missing":
        preflight_env = {key: value for key, value in env.items() if key != "SUPABASE_SECRET_KEY"}
        receipt = pilot.execute(preflight_env, path, server, preflight_only=True)
        receipt[problem] = {"counts": {}, "intents": []}.get(problem, "other")
        path.write_text(json.dumps(receipt))
    before = path.read_bytes() if path.exists() else None
    count = len(server.calls)
    assert pilot.execute(env, path, server)["error_code"] == "PILOT_PREFLIGHT_REQUIRED"
    assert len(server.calls) == count
    assert (path.read_bytes() if path.exists() else None) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("MINDX_STORAGE_PILOT_APPROVAL_SHA", ""),
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("GITHUB_REPOSITORY", "foreign/repo"),
        ("SUPABASE_URL", "https://other.supabase.co"),
    ],
)
def test_storage_synthetic_wrong_context_blocks_before_requests(tmp_path, field, value):
    env = environment()
    env[field] = value
    server = SyntheticServer()
    assert run_pilot(env, tmp_path / "receipt.json", server)["status"] == "FAILED"
    assert not server.calls


@pytest.mark.parametrize(
    "history",
    [
        {"total_count": 2, "workflow_runs": [{"id": 9}, {"id": 10}]},
        {"total_count": 101, "workflow_runs": [{"id": 10}]},
        {"total_count": 1, "workflow_runs": []},
    ],
)
def test_storage_synthetic_prior_or_ambiguous_dispatch_blocks_supabase(tmp_path, history):
    server = SyntheticServer()
    server.history = history
    assert run_pilot(environment(), tmp_path / "receipt.json", server)["status"] == "FAILED"
    assert len(server.calls) == 1


@pytest.mark.parametrize("problem", ["foreign_object", "bad_version", "members"])
def test_storage_synthetic_scope_drift_preserved(tmp_path, problem):
    server = SyntheticServer()
    setattr(server, problem, [{"user_id": "foreign-member"}] if problem == "members" else True)
    result = run_pilot(environment(), tmp_path / "receipt.json", server)
    assert result["status"] == "FAILED"
    assert result["counts"]["upload"] == result["counts"]["rpc"] == result["counts"]["delete"] == 0


def test_storage_synthetic_corrupt_download_stops_before_activation(tmp_path):
    server = SyntheticServer()
    server.corrupt_download = True
    result = run_pilot(environment(), tmp_path / "receipt.json", server)
    assert result["status"] == "FAILED"
    assert len(server.objects) == 1 and not server.versions
    assert result["counts"]["rpc"] == result["counts"]["delete"] == 0


@pytest.mark.parametrize(
    "route",
    [
        "/storage/v1/object/browser-state/",
        "/rpc/activate_browser_state_version",
        "/rpc/reset_browser_state",
        "/storage/v1/object/browser-state",
    ],
)
def test_storage_synthetic_uncertain_write_not_retried_or_auto_cleaned(tmp_path, route):
    server = SyntheticServer()
    server.fail_on = route
    result = run_pilot(environment(), tmp_path / "receipt.json", server)
    assert result["status"] == "FAILED"
    assert len(server.failed_calls) == 1
    assert result["intents"][-1]["outcome"] == "UNKNOWN"
    assert "untrusted-private-error-text" not in (tmp_path / "receipt.json").read_text()


def test_storage_synthetic_same_receipt_cannot_execute_twice(tmp_path):
    server = SyntheticServer()
    path = tmp_path / "receipt.json"
    run_pilot(environment(), path, server)
    before, count = path.read_bytes(), len(server.calls)
    assert run_pilot(environment(), path, server)["status"] == "FAILED"
    assert path.read_bytes() == before and len(server.calls) == count


def test_storage_synthetic_unknown_upload_can_exist_and_is_preserved(tmp_path):
    server = SyntheticServer()

    def uncertain_after_apply(method, url, headers, body):
        response = server(method, url, headers, body)
        if method == "POST" and "/storage/v1/object/browser-state/" in url:
            raise OSError("untrusted-private-error-text")
        return response

    result = run_pilot(environment(), tmp_path / "receipt.json", uncertain_after_apply)
    assert result["status"] == "FAILED" and len(server.objects) == 1
    assert result["counts"]["upload"] == 1
    assert result["counts"]["rpc"] == result["counts"]["delete"] == 0
    assert result["intents"][-1]["outcome"] == "UNKNOWN"


def test_storage_synthetic_foreign_object_after_reset_blocks_delete(tmp_path):
    server = SyntheticServer()

    def drift_after_reset(method, url, headers, body):
        response = server(method, url, headers, body)
        if url.endswith("/rpc/reset_browser_state"):
            server.foreign_object = True
        return response

    result = run_pilot(environment(), tmp_path / "receipt.json", drift_after_reset)
    assert result["status"] == "FAILED" and len(server.objects) == 2
    assert [version["status"] for version in server.versions] == ["revoked", "revoked"]
    assert result["counts"]["delete"] == 0


def test_storage_synthetic_redirect_is_not_followed():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/redirect-target")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = pilot.request_once(
            "GET", f"http://127.0.0.1:{server.server_port}/original", {}, None
        )
        assert response.status == 302 and calls == ["/original"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
