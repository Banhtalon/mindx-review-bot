"""Private, one-shot App session capability check. It never dispatches work."""

from __future__ import annotations

import base64
import binascii
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import BinaryIO, TextIO

PROJECT_REF = "gnvzjvgfsxfjgldatbwt"
PROJECT_URL = f"https://{PROJECT_REF}.supabase.co"
MAX_INPUT_BYTES = 8192
MIN_REMAINING_SECONDS = 60
UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)
PUBLISHABLE_KEY = re.compile(r"^sb_publishable_[A-Za-z0-9_-]{16,}$")
FIELDS = {
    "version",
    "attestation",
    "project_ref",
    "user_uuid",
    "access_token",
    "public_key",
    "expires_at",
}


def decode_claims(token: object) -> dict[str, object] | None:
    if not isinstance(token, str) or len(token) > 8192:
        return None
    parts = token.split(".")
    if len(parts) != 3 or not parts[1]:
        return None
    try:
        encoded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.b64decode(encoded, altchars=b"-_", validate=True))
        return claims if isinstance(claims, dict) else None
    except (ValueError, TypeError, binascii.Error):
        return None


def _public_key_ok(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 4096:
        return False
    if PUBLISHABLE_KEY.fullmatch(value):
        return True
    claims = decode_claims(value)
    return bool(claims and claims.get("role") == "anon")


def process_input(raw: bytes, *, now: int | None = None) -> dict[str, str]:
    waiting = {"status": "WAITING_AUTH_CAPABILITY"}
    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        return waiting
    try:
        text = raw.decode("utf-8")
        if text.endswith("\n"):
            text = text[:-1]
        if "\n" in text or "\r" in text:
            return waiting
        context = json.loads(text)
    except (UnicodeError, ValueError):
        return waiting
    if not isinstance(context, dict) or set(context) != FIELDS:
        return waiting
    if (
        context.get("version") != 1
        or isinstance(context.get("version"), bool)
        or context.get("attestation") != "getUser-confirmed"
        or context.get("project_ref") != PROJECT_REF
        or not isinstance(context.get("user_uuid"), str)
        or not UUID.fullmatch(context["user_uuid"])
        or not _public_key_ok(context.get("public_key"))
    ):
        return waiting
    claims = decode_claims(context.get("access_token"))
    expires_at = context.get("expires_at")
    expiry = claims.get("exp") if claims else None
    current = int(time.time()) if now is None else now
    if (
        not claims
        or claims.get("iss") != f"{PROJECT_URL}/auth/v1"
        or claims.get("sub") != context["user_uuid"]
        or claims.get("role") != "authenticated"
        or claims.get("aud") != "authenticated"
        or claims.get("is_anonymous") is not False
        or isinstance(expiry, bool)
        or not isinstance(expiry, int)
        or isinstance(expires_at, bool)
        or not isinstance(expires_at, int)
        or expiry != expires_at
        or expiry < current + MIN_REMAINING_SECONDS
    ):
        return waiting
    try:
        if str(Path(__file__).resolve().parent) not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
        from api_chain_operator import live_capability_status

        status = live_capability_status(
            official_session=SimpleNamespace(verified_official_app_session=True),
            approved_head=None,
            final_packet=None,
        )
    except Exception:
        return waiting
    if status == "WAITING_FINAL_SCOPE":
        return {"status": status}
    return waiting


def main(input_stream: BinaryIO | None = None, output_stream: TextIO | None = None) -> int:
    source = input_stream or sys.stdin.buffer
    output = output_stream or sys.stdout
    try:
        raw = source.read(MAX_INPUT_BYTES + 1)
        result = process_input(raw)
    except Exception:
        result = {"status": "WAITING_AUTH_CAPABILITY"}
    output.write(json.dumps(result, separators=(",", ":")) + "\n")
    output.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
