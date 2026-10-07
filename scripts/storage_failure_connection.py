"""Explicit supervised connection; credentials enter only through private stdin."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import storage_failure_pilot as pilot
from app_session_receiver import PROJECT_REF, decode_claims, process_input

MAX_INPUT = 16_384


def connection_scope(folder):
    binding = pilot.check_scope(folder)
    connection = json.loads((folder / "approval.json").read_bytes()).get("connection", {})
    pilot.require(
        set(connection) == {"mode", "project_ref", "actor_sha256"}
        and connection.get("mode") == "LOCAL_SUPERVISED"
        and connection.get("project_ref") == PROJECT_REF
        and isinstance(connection.get("actor_sha256"), str)
        and re.fullmatch(r"[a-f0-9]{64}", connection["actor_sha256"]),
        "PILOT_CONNECTION_NOT_APPROVED",
    )
    return binding, connection["actor_sha256"]


def run_private_input(
    folder, phase, raw, *, sender=pilot.previous.request_once, validate_scope=connection_scope
):
    """A trusted SDK parent supplies its confirmed principal and official stored key.

    This checks the existing attestation, not a JWT signature. No login, user lookup,
    credential file/env/argv, implicit phase transition, or credential output.
    """
    try:
        pilot.require(
            phase in {"exercise", "reconcile", "cleanup"}
            and isinstance(raw, bytes)
            and 0 < len(raw) <= MAX_INPUT,
            "PILOT_INPUT_BLOCKED",
        )
        binding, actor = validate_scope(folder)  # No input/network before approval.
        payload = json.loads(raw)
        pilot.require(
            isinstance(payload, dict) and set(payload) == {"application", "service_key"},
            "PILOT_INPUT_BLOCKED",
        )
        context, service = payload["application"], payload["service_key"]
        pilot.require(
            isinstance(service, str) and 0 < len(service) <= 4096, "PILOT_KEY_TYPE_BLOCKED"
        )
        legacy = decode_claims(service)
        pilot.require(
            re.fullmatch(r"sb_secret_[A-Za-z0-9_-]{16,}", service)
            or (
                legacy and legacy.get("role") == "service_role" and legacy.get("ref") == PROJECT_REF
            ),
            "PILOT_KEY_TYPE_BLOCKED",
        )

        def approved_scope(folder):
            current, current_actor = validate_scope(folder)
            pilot.require(current == binding and current_actor == actor, "PILOT_SOURCE_CHANGED")
            pilot.require(
                process_input(json.dumps(context).encode()).get("status") == "WAITING_FINAL_SCOPE"
                and hashlib.sha256(context["user_uuid"].encode()).hexdigest() == actor,
                "PILOT_ACTOR_BLOCKED",
            )
            return current

        approved_scope(folder)
        public = context["public_key"]
        principals = {
            "service": {"apikey": service, "Authorization": "Bearer " + service},
            "anon": {"apikey": public, "Authorization": "Bearer " + public},
            "authenticated": {
                "apikey": public,
                "Authorization": "Bearer " + context["access_token"],
            },
        }

        def send(method, url, headers, body):
            pilot.require(url.startswith(pilot.BASE_URL + "/"), "PILOT_HOST_BLOCKED")
            headers = dict(headers)
            # New API keys are not JWTs. Keep the user JWT, omit key-as-Bearer.
            if (
                headers["apikey"].startswith("sb_")
                and headers.get("Authorization") == "Bearer " + headers["apikey"]
            ):
                headers.pop("Authorization")
            return sender(method, url, headers, body)

        result = pilot.execute(
            folder, phase, principals, transport=send, validate_scope=approved_scope
        )
        return {key: result[key] for key in ("status", "counts", "error_code") if key in result}
    except Exception:
        return {"status": "BLOCKED", "error_code": "PILOT_CONNECTION_BLOCKED"}


def main(argv=None, input_stream=None, output_stream=None):
    output = output_stream or sys.stdout
    parser = argparse.ArgumentParser(description="Supervised Storage phase; private stdin only")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--phase", choices=("exercise", "reconcile", "cleanup"), required=True)
    parser.add_argument("--scope", type=Path, required=True)
    args = parser.parse_args(argv)
    result = {"status": "BLOCKED", "error_code": "PILOT_CONNECTION_BLOCKED"}
    if args.live:
        try:
            connection_scope(args.scope)  # Fail closed before opening the private input pipe.
            source = input_stream or sys.stdin.buffer
            if not source.isatty():
                result = run_private_input(args.scope, args.phase, source.read(MAX_INPUT + 1))
        except Exception:
            pass
    output.write(json.dumps(result) + "\n")
    output.flush()
    return (
        0
        if result["status"] in {"WAITING_RECONCILE", "READY_CLEANUP", "STORAGE_CLEAN_SQL_PENDING"}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
