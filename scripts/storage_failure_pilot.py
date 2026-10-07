"""Bounded P2-D2 preparation. No default network transport or live CLI."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import storage_synthetic_pilot as previous
from api_chain_continuation import check_source_head, digest, persist
from mindx_runner.browser_state import BrowserStateCipher, BrowserStateError, EncryptedStateEnvelope
from mindx_runner.supabase_client import HttpResponse, SupabaseRunnerClient

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = previous.BASE_URL
WORKSPACE = "8dfeeaf2-99f0-5475-b8fc-023960050de2"
NAME = "phase2-state-failure-synthetic-20261007"
VERSIONS = ["2ff71e45-d7aa-5577-9d9a-c77c66375a21", "e7afa6d9-96ed-5cb5-884e-e4bd0f398746"]
PATHS = [f"{WORKSPACE}/teaching/{version}.json" for version in VERSIONS]
LIMITS = {"read": 40, "download": 8, "upload": 3, "rpc": 5, "delete": 1}
SOURCES = {
    "scripts/storage_failure_pilot.py", "scripts/storage_synthetic_pilot.py",
    "scripts/storage_failure_connection.py",
    "scripts/api_chain_continuation.py", "scripts/api_chain_operator.py",
    "scripts/app_session_receiver.py",
    "apps/browser-runner/src/mindx_runner/browser_state.py",
    "apps/browser-runner/src/mindx_runner/supabase_client.py",
    *[f"scripts/fixtures/storage-pilot/{version}.json" for version in previous.VERSION_IDS],
}
VERSION_ROUTE = f"/rest/v1/browser_state_versions?workspace_id=eq.{WORKSPACE}&select=id,workspace_id,site,object_path,key_version,state_hash,status&limit=3"
ACTIVE_ROUTE = f"/rest/v1/browser_state_versions?workspace_id=eq.{WORKSPACE}&site=eq.teaching&status=eq.active&select=object_path&limit=1"
RESET_ROUTE = "/rest/v1/rpc/reset_browser_state"
RESET_BODY = {"target_workspace_id": WORKSPACE, "target_site": "teaching"}
require = previous.require


def fixtures():
    raws = [(ROOT / "scripts/fixtures/storage-pilot" / f"{v}.json").read_bytes()
            for v in previous.VERSION_IDS]
    for index, raw in enumerate(raws):
        previous.verify_fixture(raw, index)
    envelope = EncryptedStateEnvelope.from_bytes(raws[1])
    ciphertext = bytearray(envelope.ciphertext)
    ciphertext[0] ^= 1
    tampered = replace(envelope, ciphertext=bytes(ciphertext)).to_bytes()
    require(len(tampered) <= 1024, "PILOT_FIXTURE_MISMATCH")
    return raws, tampered


def activation(index):
    return {**RESET_BODY, "target_version_id": VERSIONS[index],
            "target_object_path": "browser-state/" + PATHS[index],
            "target_key_version": index + 1, "target_state_hash": previous.STATE_HASHES[index]}


def allowed(kind, role, method, path, body, raws, tampered):
    """Exact request shapes, including the one permitted overwrite and role."""
    if role != "service":
        return (kind == "rpc" and role in {"anon", "authenticated"} and
                method == "POST" and path == RESET_ROUTE and body == RESET_BODY)
    if kind == "read":
        reads = {VERSION_ROUTE, ACTIVE_ROUTE, "/storage/v1/bucket/browser-state",
                 f"/rest/v1/workspaces?id=eq.{WORKSPACE}&select=id,name&limit=2",
                 *[f"/rest/v1/{t}?workspace_id=eq.{WORKSPACE}&select=workspace_id&limit=1"
                   for t in ("workspace_members", "automation_jobs", "automation_runs")]}
        return ((method == "GET" and path in reads and body is None) or
                (method == "POST" and path == "/storage/v1/object/list/browser-state" and
                 body in [{"prefix": prefix, "limit": 3, "offset": 0}
                          for prefix in (WORKSPACE, WORKSPACE + "/teaching")]))
    if kind == "download":
        return method == "GET" and body is None and path in ["/storage/v1/object/browser-state/" + p for p in PATHS]
    if kind == "upload":
        return method == "POST" and any(
            path == "/storage/v1/object/browser-state/" + PATHS[i] and body == raw
            for i, raw in [(0, raws[0]), (1, raws[1]), (1, tampered)])
    if kind == "rpc":
        return method == "POST" and ((path == RESET_ROUTE and body == RESET_BODY) or
                (path == "/rest/v1/rpc/activate_browser_state_version" and body in [activation(0), activation(1)]))
    return (kind == "delete" and method == "DELETE" and path == "/storage/v1/object/browser-state" and
            body == {"prefixes": PATHS})


def check_scope(folder, root=ROOT):
    scope = json.loads((folder / "approval.json").read_bytes())
    require(scope.get("status") == "EXACT_SCOPE_APPROVED" and
            scope.get("workspace") == WORKSPACE and scope.get("limits") == LIMITS and
            scope.get("contract_sha256") == digest(folder / "TASK.md"), "PILOT_APPROVAL_REQUIRED")
    hashes = scope.get("source_sha256", {})
    require(set(hashes) == SOURCES and all(digest(root / name) == sha for name, sha in hashes.items()),
            "PILOT_SOURCE_CHANGED")
    check_source_head(root, scope.get("head"))
    return scope["head"], digest(folder / "approval.json")


def execute(folder, phase, principals, *, transport, validate_scope=check_scope):
    """Each phase is explicit. Unknown writes never open automatic cleanup."""
    require(phase in {"exercise", "reconcile", "cleanup"}, "PILOT_PHASE_BLOCKED")
    head, approval = validate_scope(folder)
    report = folder / "receipt.json"
    if phase == "exercise":
        receipt = {"head": head, "approval_sha256": approval, "workspace": WORKSPACE,
                   "status": "STARTED", "phases": [], "counts": dict.fromkeys(LIMITS, 0),
                   "intents": [], "checks": []}
        try:
            persist(report, receipt, exclusive=True)
        except FileExistsError:
            return {"status": "BLOCKED", "error_code": "PILOT_ALREADY_ATTEMPTED"}
    else:
        receipt = json.loads(report.read_bytes())
        require(receipt.get("status") == {"reconcile": "WAITING_RECONCILE", "cleanup": "READY_CLEANUP"}[phase]
                and receipt.get("phases") == ({"reconcile": ["exercise"], "cleanup": ["exercise", "reconcile"]}[phase])
                and receipt.get("head") == head and receipt.get("approval_sha256") == approval
                and receipt.get("workspace") == WORKSPACE, "PILOT_CONTINUATION_BLOCKED")
        require(set(receipt["counts"]) == set(LIMITS) and all(
            type(count) is int and 0 <= count <= LIMITS[kind] and
            count == sum(i.get("kind") == kind for i in receipt["intents"])
            for kind, count in receipt["counts"].items()), "PILOT_LEDGER_INVALID")
    receipt["phases"].append(phase)
    receipt["status"] = "STARTED"
    persist(report, receipt)

    def save():
        persist(report, receipt)

    try:
        raws, tampered = fixtures()
        require(set(principals) == {"service", "anon", "authenticated"} and all(
            set(p) == {"apikey", "Authorization"} and all(isinstance(v, str) and v for v in p.values())
            for p in principals.values()), "PILOT_CREDENTIAL_SCOPE")

        def send(kind, method, path, body=None, role="service", *, lose_response=False):
            require(allowed(kind, role, method, path, body, raws, tampered), "PILOT_REQUEST_BLOCKED")
            require(receipt["counts"][kind] < LIMITS[kind], "PILOT_BUDGET_EXHAUSTED")
            receipt["counts"][kind] += 1
            wire = body if isinstance(body, bytes) else (None if body is None else json.dumps(body).encode())
            intent = {"kind": kind, "role": role, "phase": phase, "method": method, "path": path,
                      "body_sha256": hashlib.sha256(wire).hexdigest() if wire is not None else None,
                      "outcome": "UNKNOWN"}
            receipt["intents"].append(intent)
            save()  # Failed/blocked sends still consume their reservation.
            require(validate_scope(folder) == (head, approval), "PILOT_SOURCE_CHANGED")
            headers = {**principals[role], "Content-Type": "application/json"}
            if kind == "upload" and body == tampered:
                headers["x-upsert"] = "true"
            response = transport(method, BASE_URL + path, headers, wire)
            require(isinstance(response, HttpResponse) and len(response.body) <= 32768, "PILOT_RESPONSE_UNKNOWN")
            if lose_response:
                receipt["status"] = "WAITING_RECONCILE"
                receipt["checks"].append("SIMULATED_ACTIVATION_RESPONSE_LOSS")
                save()
                return None  # Deliberately discard response, never resend.
            intent["outcome"] = f"HTTP_{response.status}"
            save()
            if role != "service":
                require(response.status in {401, 403} and json.loads(response.body).get("code") == "42501",
                        "PILOT_RESET_DENIAL_UNPROVEN")
            else:
                require(200 <= response.status < 300, "PILOT_REQUEST_REJECTED")
            return response

        def data(method, path, body=None):
            return json.loads(send("read", method, path, body).body)

        def inventory(expected):
            parent = data("POST", "/storage/v1/object/list/browser-state", {"prefix": WORKSPACE, "limit": 3, "offset": 0})
            children = data("POST", "/storage/v1/object/list/browser-state", {"prefix": WORKSPACE + "/teaching", "limit": 3, "offset": 0})
            require(isinstance(parent, list) and len(parent) == bool(expected) and
                    all(p.get("id") is None and p.get("name") == "teaching" for p in parent) and
                    isinstance(children, list) and len(children) == len(expected) and
                    {WORKSPACE + "/teaching/" + p["name"] for p in children} == set(expected) and
                    all(p.get("id") is not None and 0 < p.get("metadata", {}).get("size", 0) <= 1024 for p in children),
                    "PILOT_OBJECT_SCOPE_MISMATCH")

        def guard(statuses, paths):
            require(data("GET", f"/rest/v1/workspaces?id=eq.{WORKSPACE}&select=id,name&limit=2") ==
                    [{"id": WORKSPACE, "name": NAME}], "PILOT_WORKSPACE_MISMATCH")
            for table in ("workspace_members", "automation_jobs", "automation_runs"):
                require(data("GET", f"/rest/v1/{table}?workspace_id=eq.{WORKSPACE}&select=workspace_id&limit=1") == [],
                        "PILOT_WORKSPACE_NOT_ISOLATED")
            versions = data("GET", VERSION_ROUTE)
            expected = [{"id": VERSIONS[i], "workspace_id": WORKSPACE, "site": "teaching",
                         "object_path": "browser-state/" + PATHS[i], "key_version": i + 1,
                         "state_hash": previous.STATE_HASHES[i], "status": status}
                        for i, status in enumerate(statuses)]
            require(isinstance(versions, list) and sorted(versions, key=lambda v: v["id"]) ==
                    sorted(expected, key=lambda v: v["id"]), "PILOT_VERSION_SCOPE_MISMATCH")
            inventory(paths)

        def get(index):
            return send("download", "GET", "/storage/v1/object/browser-state/" + PATHS[index]).body

        def loader_transport(method, url, headers, body):
            del headers
            path = url.removeprefix(BASE_URL)
            require(url.startswith(BASE_URL + "/") and body is None, "PILOT_REQUEST_BLOCKED")
            response = send("read" if path == ACTIVE_ROUTE else "download", method, path)
            if path == ACTIVE_ROUTE:
                require(json.loads(response.body) == [{"object_path": "browser-state/" + PATHS[1]}],
                        "PILOT_ACTIVE_SCOPE_MISMATCH")
            return response

        client = SupabaseRunnerClient(BASE_URL, principals["service"]["apikey"], transport=loader_transport)

        def reject(cipher, raw, label):
            try:
                cipher.decrypt(EncryptedStateEnvelope.from_bytes(raw), site="teaching")
            except BrowserStateError:
                receipt["checks"].append(label)
                save()
                return
            require(False, "PILOT_DECRYPT_REJECTION_UNPROVEN")

        if phase == "exercise":
            bucket = data("GET", "/storage/v1/bucket/browser-state")
            require(bucket.get("id") == "browser-state" and bucket.get("public") is False, "PILOT_BUCKET_NOT_PRIVATE")
            guard([], [])
            for index, raw in enumerate(raws):
                send("upload", "POST", "/storage/v1/object/browser-state/" + PATHS[index], raw)
                response = send("rpc", "POST", "/rest/v1/rpc/activate_browser_state_version",
                                activation(index), lose_response=index == 1)
                if index == 0:
                    require(json.loads(response.body) == [{"version_id": VERSIONS[0],
                            "object_path": "browser-state/" + PATHS[0], "status": "active"}], "PILOT_ACTIVATION_UNPROVEN")
            return receipt

        guard(["revoked", "active"], PATHS)
        if phase == "reconcile":
            before = receipt["counts"].copy()
            try:
                BrowserStateCipher(b"", 2)  # Missing key must fail before active-loader I/O.
            except BrowserStateError:
                receipt["checks"].append("MISSING_KEY_ZERO_NETWORK")
            else:
                require(False, "PILOT_MISSING_KEY_UNPROVEN")
            require(receipt["counts"] == before, "PILOT_MISSING_KEY_NETWORK")
            raw1 = get(0)
            raw2 = client.load_active_browser_state(WORKSPACE, "teaching")
            require([raw1, raw2] == raws, "PILOT_OBJECT_BYTES_MISMATCH")
            key2 = hashlib.sha256(b"public-synthetic-storage-fixture-2").digest()
            reject(BrowserStateCipher(hashlib.sha256(b"wrong-public-synthetic-key").digest(), 2), raw2, "WRONG_KEY_REJECTED")
            reject(BrowserStateCipher(key2, 1), raw2, "WRONG_VERSION_REJECTED")
            reject(BrowserStateCipher(hashlib.sha256(b"public-synthetic-storage-fixture-1").digest(), 1), raw2, "ACTIVE_LOADER_OLD_KEY_REJECTED")
            for role in ("anon", "authenticated"):
                send("rpc", "POST", RESET_ROUTE, RESET_BODY, role)
            guard(["revoked", "active"], PATHS)
            require([get(0), get(1)] == raws, "PILOT_DENIAL_CHANGED_OBJECTS")
            receipt["checks"].append("HTTP_DENIAL_STATE_UNCHANGED")
            send("upload", "POST", "/storage/v1/object/browser-state/" + PATHS[1], tampered)
            stored = client.load_active_browser_state(WORKSPACE, "teaching")
            require(stored == tampered, "PILOT_TAMPER_NOT_STORED")
            reject(BrowserStateCipher(key2, 2), stored, "STORED_TAMPER_REJECTED")
            receipt["status"] = "READY_CLEANUP"
        else:
            require([get(0), get(1)] == [raws[0], tampered], "PILOT_CLEANUP_BYTES_MISMATCH")
            response = send("rpc", "POST", RESET_ROUTE, RESET_BODY)
            require(json.loads(response.body) == [{"object_path": "browser-state/" + PATHS[1]}], "PILOT_RESET_UNPROVEN")
            guard(["revoked", "revoked"], PATHS)
            send("delete", "DELETE", "/storage/v1/object/browser-state", {"prefixes": PATHS})
            inventory([])
            receipt["checks"].append("STORAGE_OBJECTS_ZERO_METADATA_SQL_PENDING")
            receipt["status"] = "STORAGE_CLEAN_SQL_PENDING"
    except Exception:
        receipt["status"] = "FAILED_STOPPED"
        receipt["error_code"] = "PILOT_STOPPED"  # Never persist exception/server/credential text.
    save()
    return receipt


if __name__ == "__main__":
    print("PREPARATION_ONLY: use the local synthetic tests; no live CLI is enabled.")
