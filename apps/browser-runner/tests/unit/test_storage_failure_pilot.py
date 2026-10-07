"""Public fixtures and fake transport only; no Supabase calls."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_storage_synthetic_pilot import SyntheticServer
from test_storage_synthetic_pilot import pilot as old

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "storage_failure_pilot", ROOT / "scripts/storage_failure_pilot.py"
)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(old, "WORKSPACE", pilot.WORKSPACE)
    monkeypatch.setattr(old, "WORKSPACE_NAME", pilot.NAME)
    (tmp_path / "TASK.md").write_text("synthetic contract")
    (tmp_path / "approval.json").write_text(json.dumps({"synthetic": True}))
    server = SyntheticServer()
    principals = {
        role: {
            "apikey": "public-synthetic-" + role,
            "Authorization": "Bearer public-synthetic-" + role,
        }
        for role in ("service", "anon", "authenticated")
    }

    def validate(folder):
        return "a" * 40, pilot.digest(folder / "approval.json")

    def transport(method, url, headers, body):
        if url.endswith(pilot.RESET_ROUTE) and headers["apikey"] != principals["service"]["apikey"]:
            server.calls.append((method, url))
            return pilot.HttpResponse(403, b'{"code":"42501"}')
        if url.endswith(pilot.ACTIVE_ROUTE):
            server.calls.append((method, url))
            rows = [
                {"object_path": v["object_path"]}
                for v in server.versions
                if v["status"] == "active"
            ]
            return pilot.HttpResponse(200, json.dumps(rows).encode())
        if headers.get("x-upsert") == "true":
            server.calls.append((method, url))
            name = url.split("/storage/v1/object/browser-state/")[1]
            assert name == pilot.PATHS[1] and name in server.objects
            server.objects[name] = body
            return pilot.HttpResponse(200, b"{}")
        return server(method, url, headers, body)

    def run(phase, sender=transport, validator=validate):
        return pilot.execute(
            tmp_path, phase, principals, transport=sender, validate_scope=validator
        )

    return tmp_path, server, run, transport, validate


def test_remaining_failure_phases_bounded_and_not_automatic(setup):
    folder, server, run, _, _ = setup
    first = run("exercise")
    assert first["status"] == "WAITING_RECONCILE"
    assert first["intents"][-1]["outcome"] == "UNKNOWN"
    assert len(server.objects) == 2 and len(server.rpc_names) == 2
    assert first["counts"]["delete"] == 0
    assert run("reconcile")["status"] == "READY_CLEANUP"
    final = run("cleanup")
    assert final["status"] == "STORAGE_CLEAN_SQL_PENDING"
    assert final["counts"] == {"read": 40, "download": 7, "upload": 3, "rpc": 5, "delete": 1}
    assert set(final["checks"]) == {
        "SIMULATED_ACTIVATION_RESPONSE_LOSS",
        "MISSING_KEY_ZERO_NETWORK",
        "WRONG_KEY_REJECTED",
        "WRONG_VERSION_REJECTED",
        "ACTIVE_LOADER_OLD_KEY_REJECTED",
        "HTTP_DENIAL_STATE_UNCHANGED",
        "STORED_TAMPER_REJECTED",
        "STORAGE_OBJECTS_ZERO_METADATA_SQL_PENDING",
    }
    assert not server.objects and all(v["status"] == "revoked" for v in server.versions)
    raw = (folder / "receipt.json").read_text()
    assert "Bearer" not in raw and "public-synthetic-service" not in raw


def test_no_repeat_or_skipped_reconciliation(setup):
    folder, server, run, _, _ = setup
    run("exercise")
    before, count = (folder / "receipt.json").read_bytes(), len(server.calls)
    assert run("exercise")["error_code"] == "PILOT_ALREADY_ATTEMPTED"
    with pytest.raises(pilot.previous.PilotBlocked):
        run("cleanup")
    assert (folder / "receipt.json").read_bytes() == before and len(server.calls) == count
    run("reconcile")
    before, count = (folder / "receipt.json").read_bytes(), len(server.calls)
    with pytest.raises(pilot.previous.PilotBlocked):
        run("reconcile")
    assert (folder / "receipt.json").read_bytes() == before and len(server.calls) == count


@pytest.mark.parametrize("phase", ["exercise", "reconcile", "cleanup"])
def test_unknown_write_preserves_objects_without_retry(setup, phase):
    folder, server, run, transport, _ = setup
    if phase != "exercise":
        run("exercise")
    if phase == "cleanup":
        run("reconcile")
    failures = []

    def unknown(method, url, headers, body):
        response = transport(method, url, headers, body)
        if method != "GET" and ("/rpc/" in url or "/object/browser-state/" in url):
            failures.append(url)
            raise OSError("untrusted-private-error-text")
        return response

    result = run(phase, unknown)
    assert result["status"] == "FAILED_STOPPED" and len(failures) == 1
    assert result["intents"][-1]["outcome"] == "UNKNOWN" and result["counts"]["delete"] == 0
    count = len(server.calls)
    if phase != "exercise":
        with pytest.raises(pilot.previous.PilotBlocked):
            run(phase)
    else:
        assert run(phase)["status"] == "BLOCKED"
    assert len(server.calls) == count
    assert "untrusted-private-error-text" not in (folder / "receipt.json").read_text()


@pytest.mark.parametrize("problem", ["foreign_object", "members", "bad_version", "bytes"])
def test_scope_drift_blocks_cleanup(setup, problem):
    _, server, run, _, _ = setup
    run("exercise")
    run("reconcile")
    if problem == "bytes":
        server.objects[pilot.PATHS[0]] += b"corrupt"
    else:
        setattr(server, problem, [{"user_id": "foreign"}] if problem == "members" else True)
    result = run("cleanup")
    assert result["status"] == "FAILED_STOPPED" and result["counts"]["delete"] == 0
    assert len(server.objects) == 2


def test_valid_approval_replacement_between_requests_stops(setup):
    folder, server, run, transport, _ = setup

    def changed(method, url, headers, body):
        response = transport(method, url, headers, body)
        (folder / "approval.json").write_text(json.dumps({"synthetic": True, "revision": 2}))
        return response

    result = run("exercise", changed)
    assert result["status"] == "FAILED_STOPPED" and len(server.calls) == 1
    assert result["counts"]["read"] == 2 and result["intents"][-1]["outcome"] == "UNKNOWN"


def test_budget_exhaustion_cannot_be_reset_by_new_phase(setup):
    folder, server, run, _, _ = setup
    run("exercise")
    ledger = json.loads((folder / "receipt.json").read_text())
    while ledger["counts"]["read"] < pilot.LIMITS["read"]:
        ledger["counts"]["read"] += 1
        ledger["intents"].append({"kind": "read", "outcome": "UNKNOWN"})
    (folder / "receipt.json").write_text(json.dumps(ledger))
    count = len(server.calls)
    assert run("reconcile")["status"] == "FAILED_STOPPED" and len(server.calls) == count


def test_exact_request_allowlist():
    raws, tampered = pilot.fixtures()
    assert pilot.allowed("rpc", "anon", "POST", pilot.RESET_ROUTE, pilot.RESET_BODY, raws, tampered)
    for role, method, path, body in [
        ("anon", "POST", "/rest/v1/rpc/activate_browser_state_version", pilot.activation(0)),
        ("service", "DELETE", "/storage/v1/object/browser-state", {"prefixes": pilot.PATHS[:1]}),
        ("service", "POST", pilot.RESET_ROUTE, {**pilot.RESET_BODY, "target_site": "lms"}),
        ("service", "POST", "/storage/v1/object/browser-state/foreign", raws[0]),
    ]:
        assert not pilot.allowed(
            "rpc" if "rpc" in path else "delete", role, method, path, body, raws, tampered
        )


@pytest.mark.parametrize(
    "response", [pilot.HttpResponse(200, b"[]"), pilot.HttpResponse(403, b'{"code":"unknown"}')]
)
def test_reset_denial_requires_explicit_permission_code(setup, response):
    _, server, run, transport, _ = setup
    run("exercise")

    def ambiguous(method, url, headers, body):
        if url.endswith(pilot.RESET_ROUTE):
            server.calls.append((method, url))
            return response
        return transport(method, url, headers, body)

    result = run("reconcile", ambiguous)
    assert result["status"] == "FAILED_STOPPED" and result["counts"]["delete"] == 0
    assert "HTTP_DENIAL_STATE_UNCHANGED" not in result["checks"]


def test_changed_approval_before_next_phase_preserves_receipt(setup):
    folder, server, run, _, _ = setup
    run("exercise")
    before, count = (folder / "receipt.json").read_bytes(), len(server.calls)
    (folder / "approval.json").write_text(json.dumps({"synthetic": True, "revision": 2}))
    with pytest.raises(pilot.previous.PilotBlocked):
        run("reconcile")
    assert (folder / "receipt.json").read_bytes() == before and len(server.calls) == count


def test_real_source_guard_approval_hash_head_and_dirty_tree(tmp_path):
    from api_chain_continuation import GIT

    for name in pilot.SOURCES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    git = GIT

    def command(*args):
        return (
            subprocess.run([git, *args], cwd=tmp_path, check=True, capture_output=True)
            .stdout.decode()
            .strip()
        )

    command("init")
    command("add", ".")
    command(
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=synthetic@example.invalid",
        "commit",
        "-m",
        "synthetic source",
    )
    folder = tmp_path / ".workflow-local"
    folder.mkdir()
    (folder / "TASK.md").write_text("synthetic contract")
    scope = {
        "status": "EXACT_SCOPE_APPROVED",
        "workspace": pilot.WORKSPACE,
        "limits": pilot.LIMITS,
        "contract_sha256": pilot.digest(folder / "TASK.md"),
        "head": command("rev-parse", "HEAD"),
        "source_sha256": {name: pilot.digest(tmp_path / name) for name in pilot.SOURCES},
    }
    (folder / "approval.json").write_text(json.dumps(scope))
    assert pilot.check_scope(folder, tmp_path)[0] == scope["head"]
    scope["head"] = "b" * 40
    (folder / "approval.json").write_text(json.dumps(scope))
    with pytest.raises(ValueError, match="EXACT_HEAD_CHANGED"):
        pilot.check_scope(folder, tmp_path)
    scope["head"] = command("rev-parse", "HEAD")
    target = tmp_path / "scripts/storage_failure_pilot.py"
    target.write_bytes(target.read_bytes() + b"\n# changed source\n")
    scope["source_sha256"]["scripts/storage_failure_pilot.py"] = pilot.digest(target)
    (folder / "approval.json").write_text(json.dumps(scope))
    with pytest.raises(ValueError, match="EXACT_HEAD_CHANGED"):
        pilot.check_scope(folder, tmp_path)  # Even updated hashes cannot approve a dirty tree.
