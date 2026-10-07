"""Private connection tests use unsigned synthetic claims and a fake server."""

import base64
import hashlib
import io
import json
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
import storage_failure_connection as connection
import test_storage_failure_pilot as cases


@pytest.fixture
def setup(tmp_path, monkeypatch):
    return cases.setup.__wrapped__(tmp_path, monkeypatch)


def private_payload():
    actor = "10000000-0000-4000-8000-000000000001"
    expiry = int(time.time()) + 3600
    claims = {
        "iss": connection.pilot.BASE_URL + "/auth/v1",
        "sub": actor,
        "role": "authenticated",
        "aud": "authenticated",
        "is_anonymous": False,
        "exp": expiry,
    }
    token = "e30." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return {
        "service_key": "sb_secret_public-synthetic-service-key",
        "application": {
            "version": 1,
            "attestation": "getUser-confirmed",
            "project_ref": connection.PROJECT_REF,
            "user_uuid": actor,
            "access_token": token + ".synthetic-signature",
            "public_key": "sb_publishable_public-synthetic-project-key",
            "expires_at": expiry,
        },
    }


def test_private_connection_runs_three_explicit_fake_phases(setup):
    folder, server, _, transport, validate = setup
    payload = private_payload()
    actor_hash = hashlib.sha256(payload["application"]["user_uuid"].encode()).hexdigest()
    observed = []

    def approved(folder):
        return validate(folder), actor_hash

    def sender(method, url, headers, body):
        # Assert header projection, then translate to the reused fake server's role labels.
        if headers["apikey"].startswith("sb_secret_"):
            assert "Authorization" not in headers
            role = "service"
        elif "Authorization" not in headers:
            role = "anon"
        else:
            assert headers["Authorization"] == "Bearer " + payload["application"]["access_token"]
            role = "authenticated"
        observed.append(role)
        safe = {**headers, "apikey": "public-synthetic-" + role}
        return transport(method, url, safe, body)

    raw = json.dumps(payload).encode()
    results = []
    for phase in ("exercise", "reconcile", "cleanup"):
        results.append(
            connection.run_private_input(folder, phase, raw, sender=sender, validate_scope=approved)
        )
    assert [r["status"] for r in results] == [
        "WAITING_RECONCILE",
        "READY_CLEANUP",
        "STORAGE_CLEAN_SQL_PENDING",
    ]
    assert len(observed) == 56 and observed.count("anon") == observed.count("authenticated") == 1
    assert not server.objects
    output = json.dumps(results) + (folder / "receipt.json").read_text()
    for field in ("service_key", "access_token", "public_key", "user_uuid"):
        assert payload.get(field, payload["application"].get(field)) not in output


@pytest.mark.parametrize(
    "problem", ["wrong_actor", "expired", "anonymous", "public_service_key", "missing", "oversized"]
)
def test_invalid_private_principal_blocks_before_network_or_receipt(setup, problem):
    folder, server, _, transport, validate = setup
    payload = private_payload()
    actor_hash = hashlib.sha256(payload["application"]["user_uuid"].encode()).hexdigest()
    if problem == "wrong_actor":
        actor_hash = "b" * 64
    elif problem == "expired":
        payload["application"]["expires_at"] = 1
    elif problem == "anonymous":
        payload["application"]["attestation"] = "unverified"
    elif problem == "public_service_key":
        payload["service_key"] = payload["application"]["public_key"]
    elif problem == "missing":
        del payload["application"]
    raw = (
        json.dumps(payload).encode()
        if problem != "oversized"
        else b"x" * (connection.MAX_INPUT + 1)
    )
    result = connection.run_private_input(
        folder,
        "exercise",
        raw,
        sender=transport,
        validate_scope=lambda f: (validate(f), actor_hash),
    )
    assert result["status"] == "BLOCKED" and not server.calls
    assert not (folder / "receipt.json").exists()


def test_expiry_between_sends_consumes_reservation_and_stops(setup, monkeypatch):
    folder, server, _, transport, validate = setup
    payload = private_payload()
    actor_hash = hashlib.sha256(payload["application"]["user_uuid"].encode()).hexdigest()

    def sender(method, url, headers, body):
        response = transport(method, url, headers, body)
        monkeypatch.setattr(
            connection, "process_input", lambda raw: {"status": "WAITING_AUTH_CAPABILITY"}
        )
        return response

    result = connection.run_private_input(
        folder,
        "exercise",
        json.dumps(payload).encode(),
        sender=sender,
        validate_scope=lambda f: (validate(f), actor_hash),
    )
    assert result["status"] == "FAILED_STOPPED" and len(server.calls) == 1
    ledger = json.loads((folder / "receipt.json").read_text())
    assert ledger["counts"]["read"] == 2 and ledger["intents"][-1]["outcome"] == "UNKNOWN"


def test_live_cli_requires_approved_scope_and_never_echoes_stdin(tmp_path):
    script = connection.pilot.ROOT / "scripts/storage_failure_connection.py"
    sentinel = "private-synthetic-input-must-not-appear"
    result = subprocess.run(
        [sys.executable, str(script), "--live", "--phase", "exercise", "--scope", str(tmp_path)],
        input=sentinel,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 1 and json.loads(result.stdout)["status"] == "BLOCKED"
    assert sentinel not in result.stdout + result.stderr and result.stderr == ""
    assert not (tmp_path / "receipt.json").exists()


def test_cli_without_live_does_not_read_input_or_check_scope(tmp_path):
    class Unreadable(io.BytesIO):
        def read(self, *args):
            pytest.fail("Private input must not be read without --live")

    output = io.StringIO()
    assert (
        connection.main(["--phase", "exercise", "--scope", str(tmp_path)], Unreadable(), output)
        == 1
    )
    assert json.loads(output.getvalue())["status"] == "BLOCKED"


def test_connection_scope_rejects_missing_connection_binding(setup, monkeypatch):
    folder, _, _, _, validate = setup
    monkeypatch.setattr(connection.pilot, "check_scope", validate)
    with pytest.raises(connection.pilot.previous.PilotBlocked):
        connection.connection_scope(folder)


@pytest.mark.parametrize("status", [302, 200])
def test_reused_transport_redirect_and_response_bound_on_localhost(status):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            self.send_response(status)
            if status == 302:
                self.send_header("Location", "/must-not-follow")
            self.end_headers()
            if status == 200:
                self.wfile.write(b"x" * 32769)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/original"
        if status == 302:
            assert connection.pilot.previous.request_once("GET", url, {}, None).status == 302
        else:
            with pytest.raises(connection.pilot.previous.PilotBlocked):
                connection.pilot.previous.request_once("GET", url, {}, None)
        assert calls == ["/original"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_reused_transport_timeout_is_bounded_and_not_retried(monkeypatch):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(timeout)
            raise TimeoutError("untrusted-private-timeout")

    monkeypatch.setattr(connection.pilot.previous, "build_opener", lambda *args: Opener())
    with pytest.raises(TimeoutError):
        connection.pilot.previous.request_once("GET", "http://127.0.0.1/original", {}, None)
    assert calls == [30]
