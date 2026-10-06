import base64
import importlib.util
import io
import json
import time
from pathlib import Path

import pytest

RECEIVER_PATH = Path(__file__).resolve().parents[4] / "scripts" / "app_session_receiver.py"
SPEC = importlib.util.spec_from_file_location("app_session_receiver", RECEIVER_PATH)
receiver = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(receiver)

PROJECT_REF = "gnvzjvgfsxfjgldatbwt"
USER_UUID = "1c2a7a18-6bb8-4ab1-9f29-3117f3670864"
PUBLIC_KEY = "sb_publishable_synthetic_public_key_1234567890"


def _check(condition: bool, code: str) -> None:
    if not condition:
        raise AssertionError(code)


def _token(**changes: object) -> str:
    now = int(time.time())
    claims = {
        "iss": f"https://{PROJECT_REF}.supabase.co/auth/v1",
        "sub": USER_UUID,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": now + 1800,
    }
    claims.update(changes)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{payload}.synthetic-signature"


def _context(token: str | None = None) -> dict[str, object]:
    access_token = token or _token()
    claims = receiver.decode_claims(access_token)
    _check(claims is not None, "SAFE_TEST_TOKEN_CLAIMS")
    return {
        "version": 1,
        "attestation": "getUser-confirmed",
        "project_ref": PROJECT_REF,
        "user_uuid": USER_UUID,
        "access_token": access_token,
        "public_key": PUBLIC_KEY,
        "expires_at": claims["exp"],
    }


def test_verified_pipe_context_only_reports_waiting_for_final_scope() -> None:
    context = _context()
    output = receiver.process_input(json.dumps(context).encode())
    _check(output == {"status": "WAITING_FINAL_SCOPE"}, "SAFE_VERIFIED_PIPE_STATUS")
    rendered = json.dumps(output)
    _check(USER_UUID not in rendered, "SAFE_USER_UUID_REDACTED")
    _check(str(context["access_token"]) not in rendered, "SAFE_ACCESS_TOKEN_REDACTED")
    _check(PUBLIC_KEY not in rendered, "SAFE_PUBLIC_KEY_REDACTED")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(attestation="synthetic-preview"),
        lambda value: value.update(user_uuid="2d7ad7e5-e496-44dc-86ed-9a161a86a350"),
        lambda value: value.update(public_key="sb_secret_service_role_value_123"),
        lambda value: value.update(expires_at=1),
        lambda value: value.update(password="must-never-cross-pipe"),
    ],
)
def test_unverified_or_mismatched_context_fails_closed_without_echo(mutate) -> None:
    context = _context()
    mutate(context)
    output = receiver.process_input(json.dumps(context).encode())
    _check(output == {"status": "WAITING_AUTH_CAPABILITY"}, "SAFE_REJECTED_CONTEXT_STATUS")
    _check("must-never-cross-pipe" not in json.dumps(output), "SAFE_REJECTED_CONTEXT_REDACTED")


@pytest.mark.parametrize(
    "claims",
    [
        {"role": "anon"},
        {"aud": "anon"},
        {"iss": "https://other.supabase.co/auth/v1"},
        {"exp": int(time.time()) + 5},
    ],
)
def test_jwt_claims_are_consistency_checked_against_confirmed_context(claims) -> None:
    output = receiver.process_input(json.dumps(_context(_token(**claims))).encode())
    _check(output == {"status": "WAITING_AUTH_CAPABILITY"}, "SAFE_JWT_REJECTED_STATUS")


def test_malformed_oversized_and_extra_pipe_data_are_safe() -> None:
    _check(
        receiver.process_input(b"not json") == {"status": "WAITING_AUTH_CAPABILITY"},
        "SAFE_MALFORMED_INPUT",
    )
    _check(
        receiver.process_input(b"x" * (receiver.MAX_INPUT_BYTES + 1))
        == {"status": "WAITING_AUTH_CAPABILITY"},
        "SAFE_OVERSIZED_INPUT",
    )
    _check(
        receiver.process_input(json.dumps(_context()).encode() + b"\n{}\n")
        == {"status": "WAITING_AUTH_CAPABILITY"},
        "SAFE_EXTRA_INPUT",
    )


def test_main_writes_only_safe_status_and_swallows_raw_exception_text() -> None:
    private_value = "synthetic-private-value"
    output = io.StringIO()
    receiver.main(io.BytesIO(private_value.encode()), output)
    rendered = output.getvalue()
    _check(rendered == '{"status":"WAITING_AUTH_CAPABILITY"}\n', "SAFE_MAIN_OUTPUT")
    _check(private_value not in rendered, "SAFE_MAIN_REDACTION")
