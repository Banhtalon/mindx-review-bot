"""One bounded API-backed synthetic run; never a Teaching/LMS runner."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SOURCE = ROOT / "apps/browser-runner/src"
for entry in (str(SCRIPTS), str(SOURCE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import runtime_synthetic_pilot as runtime_helpers  # noqa: E402
from storage_synthetic_pilot import request_once  # noqa: E402
from mindx_runner.supabase_client import HttpResponse, SupabaseRunnerClient  # noqa: E402

REPOSITORY = "Banhtalon/mindx-review-bot"
WORKFLOW = "spike0-dispatch-probe"
WORKFLOW_FILE = "spike0-dispatch-probe.yml"
APPROVAL = "MINDX_API_CHAIN_PILOT_APPROVAL_SHA"
BASE_URL = "https://gnvzjvgfsxfjgldatbwt.supabase.co"
BASE_ORIGIN = "https://gnvzjvgfsxfjgldatbwt.supabase.co"
WORKSPACE_ID = "50318d02-6840-457d-b5a6-0870e7a308a4"
WORKSPACE_NAME = "phase2-api-chain-synthetic-20261006-r1"
JOB_ID = "a3fed449-7fac-422f-a3a7-9b22be678c12"
JOB_TYPE = "sync_teaching"
IDEMPOTENCY_KEY = "phase2-api-chain-20261006-r1"
PAYLOAD = {"synthetic": True, "pilot_id": IDEMPOTENCY_KEY, "case": "success"}
RUNNER_ID = "api-chain-synthetic-r1"
HISTORY_URL = (
    f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/{WORKFLOW_FILE}"
    "/runs?event=workflow_dispatch&per_page=100"
)
MAX_HISTORY_RUNS = 100
MAX_RESPONSE_BYTES = 32_768
HOLD_SECONDS = 650
WALL_SECONDS = 720
HEARTBEAT_SECONDS = 30
MAX_REQUESTS = 26
MAX_HEARTBEATS = 22
JOB_PREFLIGHT_PATH = (
    "/rest/v1/automation_jobs"
    f"?id=eq.{JOB_ID}"
    "&select=id,workspace_id,type,status,idempotency_key,payload_json,max_attempts,"
    "attempt_count,runner_id,lease_expires_at,heartbeat_at&limit=2"
)
STATE_PREFLIGHT_PATH = (
    "/rest/v1/browser_state_versions"
    f"?workspace_id=eq.{WORKSPACE_ID}&select=id,site,status&limit=2"
)
RPC_PATHS = {
    "claim": "/rest/v1/rpc/claim_automation_job_run",
    "heartbeat": "/rest/v1/rpc/heartbeat_automation_job",
    "finish": "/rest/v1/rpc/finish_automation_job_run",
}
REQUEST_CAPS = {
    "job_preflight": 1,
    "state_preflight": 1,
    "claim": 1,
    "heartbeat": MAX_HEARTBEATS,
    "finish": 1,
}


class PilotBlocked(RuntimeError):
    """A fixed safety gate stopped the pilot."""


def require(condition: object, code: str) -> None:
    if not condition:
        raise PilotBlocked(code)


def persist(file: Path, value: dict[str, object]) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


def _unique_json(raw: bytes) -> object:
    def object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            require(key not in result, "PILOT_JSON_INVALID")
            result[key] = value
        return result

    return json.loads(raw.decode("utf-8"), object_pairs_hook=object_from_pairs)


def context(environment: dict[str, str], *, preflight: bool = False) -> tuple[str, str]:
    require(
        environment.get("GITHUB_REPOSITORY") == REPOSITORY
        and environment.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and environment.get("GITHUB_REF") == "refs/heads/main"
        and environment.get("GITHUB_RUN_ATTEMPT") == "1"
        and environment.get("JOB_ID") == JOB_ID
        and environment.get("JOB_TYPE") == JOB_TYPE,
        "PILOT_CONTEXT_BLOCKED",
    )
    head = environment.get("GITHUB_SHA", "")
    run_id = environment.get("GITHUB_RUN_ID", "")
    require(
        re.fullmatch(r"[a-f0-9]{40}", head) is not None
        and environment.get(APPROVAL) == head
        and re.fullmatch(r"[1-9][0-9]*", run_id) is not None,
        "PILOT_APPROVAL_REQUIRED",
    )
    supplied_url = environment.get("SUPABASE_URL")
    require(supplied_url in {None, BASE_URL}, "PILOT_ENDPOINT_BLOCKED")
    require(
        not any(
            key.upper().startswith(("TEACHING_", "LMS_"))
            or key.upper() in {"MINDX_TEACHING_TARGET_JSON", "SUPABASE_SERVICE_ROLE_KEY"}
            for key in environment
        ),
        "PILOT_ACCOUNT_ENV_BLOCKED",
    )
    if preflight:
        require(bool(environment.get("GITHUB_TOKEN")), "PILOT_HISTORY_CREDENTIAL_REQUIRED")
    else:
        require("GITHUB_TOKEN" not in environment, "PILOT_TOKEN_SCOPE_BLOCKED")
        require(bool(environment.get("SUPABASE_SECRET_KEY")), "PILOT_RUNNER_KEY_REQUIRED")
        require(
            "BROWSER_STATE_ENCRYPTION_KEY" not in environment,
            "PILOT_REAL_STATE_KEY_BLOCKED",
        )
    return head, run_id


def history_once(token: str) -> HttpResponse:
    return request_once(
        "GET",
        HISTORY_URL,
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        None,
    )


def preflight(
    environment: dict[str, str],
    file: Path,
    transport=history_once,
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "status": "PREFLIGHT_STARTED",
        "history_reads": 0,
        "history_outcome": "NOT_SENT",
        "cases": [],
    }
    file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with file.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        return {"status": "BLOCKED", "error_code": "PILOT_ALREADY_ATTEMPTED"}

    try:
        head, run_id = context(environment, preflight=True)
        receipt.update(head=head, run_id=run_id, job_id=JOB_ID, job_type=JOB_TYPE)
        receipt["history_reads"] = 1
        receipt["history_outcome"] = "UNKNOWN"
        persist(file, receipt)  # The read is consumed before its only send.
        response = transport(environment["GITHUB_TOKEN"])
        if isinstance(response, HttpResponse):
            require(response.status == 200, "PILOT_HISTORY_REJECTED")
            raw = response.body
        else:
            raw = response
        require(isinstance(raw, bytes) and len(raw) <= MAX_RESPONSE_BYTES, "PILOT_HISTORY_INVALID")
        history = _unique_json(raw)
        require(isinstance(history, dict), "PILOT_HISTORY_INVALID")
        runs = history.get("workflow_runs")
        total = history.get("total_count")
        require(
            type(total) is int
            and 0 < total <= MAX_HISTORY_RUNS
            and isinstance(runs, list)
            and len(runs) == total,
            "PILOT_HISTORY_INCOMPLETE",
        )
        matches = [
            run
            for run in runs
            if isinstance(run, dict)
            and isinstance(run.get("display_title"), str)
            and JOB_ID in run["display_title"]
        ]
        require(len(matches) == 1, "PILOT_HISTORY_AMBIGUOUS")
        run = matches[0]
        path = run.get("path")
        require(
            type(run.get("id")) is int
            and run["id"] == int(run_id)
            and run.get("name") == WORKFLOW
            and run.get("head_sha") == head
            and run.get("head_branch") == "main"
            and run.get("event") == "workflow_dispatch"
            and type(run.get("run_attempt")) is int
            and run["run_attempt"] == 1
            and type(run.get("run_number")) is int
            and run["run_number"] > 0
            and path == f".github/workflows/{WORKFLOW_FILE}",
            "PILOT_HISTORY_CONTEXT_MISMATCH",
        )
        receipt.update(
            status="PREFLIGHT_PASS",
            history_outcome="ONE_FIXED_JOB_RUN_CONFIRMED",
            run_number=run["run_number"],
        )
    except PilotBlocked as error:
        receipt.update(status="BLOCKED", error_code=str(error))
    except Exception:
        receipt.update(status="BLOCKED", error_code="PILOT_HISTORY_UNKNOWN")
        if receipt["history_reads"]:
            receipt["history_outcome"] = "UNKNOWN"
    persist(file, receipt)
    return receipt


def consume_preflight(environment: dict[str, str], file: Path) -> dict[str, object]:
    head, run_id = context(environment)
    try:
        receipt = json.loads(file.read_text(encoding="utf-8"))
    except Exception as error:
        raise PilotBlocked("PILOT_PREFLIGHT_INVALID") from error
    require(
        isinstance(receipt, dict)
        and receipt.get("status") == "PREFLIGHT_PASS"
        and receipt.get("head") == head
        and receipt.get("run_id") == run_id
        and receipt.get("job_id") == JOB_ID
        and receipt.get("job_type") == JOB_TYPE
        and receipt.get("history_reads") == 1
        and receipt.get("history_outcome") == "ONE_FIXED_JOB_RUN_CONFIRMED",
        "PILOT_PREFLIGHT_REQUIRED",
    )
    receipt.update(
        status="WORKER_STARTED",
        request_count=0,
        counts=dict.fromkeys(REQUEST_CAPS, 0),
        intents=[],
        server_snapshots=[],
        cli_outcome={"status": "NOT_STARTED"},
    )
    persist(file, receipt)
    return receipt


def _canonical_body(body: bytes | None) -> object:
    require(body is not None and len(body) <= 4096, "PILOT_REQUEST_BODY_BLOCKED")
    value = _unique_json(body)
    require(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode() == body,
        "PILOT_REQUEST_BODY_BLOCKED",
    )
    return value


def _uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def _server_time(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 40:
        return False
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.tzinfo is not None and stamp.utcoffset() is not None
    except ValueError:
        return False


def new_worker_receipt(head: str, run_id: str) -> dict[str, object]:
    return {
        "status": "WORKER_STARTED",
        "head": head,
        "run_id": run_id,
        "job_id": JOB_ID,
        "job_type": JOB_TYPE,
        "request_count": 0,
        "counts": dict.fromkeys(REQUEST_CAPS, 0),
        "intents": [],
        "server_snapshots": [],
        "cli_outcome": {"status": "NOT_STARTED"},
    }


class WorkerApiTransport:
    """Allowlisted one-send transport around the existing real Supabase client."""

    def __init__(self, receipt: dict[str, object], file: Path, sender=request_once):
        self.receipt = receipt
        self.file = file
        self.sender = sender
        self.actual_run_id: str | None = None
        started = receipt.get("worker_started_monotonic")
        self.started_monotonic = started if isinstance(started, (float, int)) else time.monotonic()

    def client(self, secret_key: str) -> SupabaseRunnerClient:
        return SupabaseRunnerClient(BASE_URL, secret_key, transport=self)

    def _classify(self, method: str, path: str, body: bytes | None) -> str:
        if method == "GET" and path == JOB_PREFLIGHT_PATH:
            return "job_preflight"
        if method == "GET" and path == STATE_PREFLIGHT_PATH:
            return "state_preflight"
        rpc = next((name for name, rpc_path in RPC_PATHS.items() if path == rpc_path), None)
        if method != "POST" or rpc is None:
            raise PilotBlocked("PILOT_REQUEST_PATH_BLOCKED")
        value = _canonical_body(body)
        if rpc == "claim":
            expected = {"target_job_id": JOB_ID, "target_runner_id": RUNNER_ID}
            require(value == expected, "PILOT_REQUEST_BODY_BLOCKED")
        elif rpc == "heartbeat":
            require(self.actual_run_id is not None, "PILOT_HEARTBEAT_WITHOUT_CLAIM")
            expected = {"target_job_id": JOB_ID, "target_runner_id": RUNNER_ID}
            require(value == expected, "PILOT_REQUEST_BODY_BLOCKED")
        else:
            require(self.actual_run_id is not None, "PILOT_FINISH_WITHOUT_CLAIM")
            expected = {
                "target_run_id": self.actual_run_id,
                "target_runner_id": RUNNER_ID,
                "target_status": "succeeded",
                "target_records_read": 0,
                "target_error_code": None,
                "target_duration_ms": value.get("target_duration_ms")
                if isinstance(value, dict)
                else None,
            }
            require(
                isinstance(value, dict)
                and type(value.get("target_duration_ms")) is int
                and value["target_duration_ms"] >= HOLD_SECONDS * 1000
                and value == expected,
                "PILOT_REQUEST_BODY_BLOCKED",
            )
        return rpc

    def _snapshot(self, kind: str, response: HttpResponse) -> None:
        if response.status != 200 or len(response.body) > MAX_RESPONSE_BYTES:
            return
        try:
            value = _unique_json(response.body)
            require(isinstance(value, list) and len(value) == 1, "PILOT_RESPONSE_INVALID")
            row = value[0]
            require(isinstance(row, dict), "PILOT_RESPONSE_INVALID")
            if kind == "claim":
                require(
                    row.get("claimed") is True
                    and row.get("job_id") == JOB_ID
                    and row.get("workspace_id") == WORKSPACE_ID
                    and row.get("job_type") == JOB_TYPE
                    and row.get("payload_json") == PAYLOAD
                    and row.get("runner_id") == RUNNER_ID
                    and type(row.get("attempt")) is int
                    and row["attempt"] == 1
                    and _uuid(row.get("run_id"))
                    and _server_time(row.get("lease_expires_at")),
                    "PILOT_RESPONSE_INVALID",
                )
                self.actual_run_id = row["run_id"]
                snapshot = {
                    "kind": kind,
                    "job_id": JOB_ID,
                    "run_id": self.actual_run_id,
                    "workspace_id": WORKSPACE_ID,
                    "runner_id": RUNNER_ID,
                    "attempt": 1,
                    "lease_expires_at": row["lease_expires_at"],
                }
            elif kind == "heartbeat":
                require(
                    self.actual_run_id is not None
                    and
                    row.get("job_id") == JOB_ID
                    and row.get("runner_id") == RUNNER_ID
                    and _server_time(row.get("lease_expires_at")),
                    "PILOT_RESPONSE_INVALID",
                )
                snapshot = {
                    "kind": kind,
                    "job_id": JOB_ID,
                    "run_id": self.actual_run_id,
                    "workspace_id": WORKSPACE_ID,
                    "runner_id": RUNNER_ID,
                    "lease_expires_at": row["lease_expires_at"],
                }
            else:
                require(
                    kind == "finish"
                    and self.actual_run_id is not None
                    and row.get("status") == "succeeded",
                    "PILOT_FINISH_STATUS_UNCONFIRMED",
                )
                self.receipt["finish_result"] = "succeeded"
                snapshot = {
                    "kind": kind,
                    "run_id": self.actual_run_id,
                    "status": "succeeded",
                }
            snapshots = self.receipt["server_snapshots"]
            assert isinstance(snapshots, list)
            snapshots.append(snapshot)
            return True
        except Exception:
            # Metadata is recorded only after strict field and format validation.
            intent = self.receipt["intents"][-1]
            assert isinstance(intent, dict)
            intent["metadata"] = "MALFORMED_OR_UNAVAILABLE"
            return False

    def __call__(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> HttpResponse:
        parsed = urlsplit(url)
        require(
            parsed.scheme == "https"
            and parsed.netloc == "gnvzjvgfsxfjgldatbwt.supabase.co"
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and parsed.fragment == "",
            "PILOT_ENDPOINT_BLOCKED",
        )
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        kind = self._classify(method.upper(), path, body)
        require(kind in REQUEST_CAPS, "PILOT_REQUEST_PATH_BLOCKED")
        counts = self.receipt["counts"]
        intents = self.receipt["intents"]
        assert isinstance(counts, dict) and isinstance(intents, list)
        require(
            self.receipt["request_count"] < MAX_REQUESTS
            and counts[kind] < REQUEST_CAPS[kind],
            "PILOT_REQUEST_BUDGET_EXCEEDED",
        )
        counts[kind] += 1
        self.receipt["request_count"] += 1
        intent: dict[str, object] = {
            "ordinal": self.receipt["request_count"],
            "kind": kind,
            "method": method.upper(),
            "path": path,
            "body_sha256": hashlib.sha256(body).hexdigest() if body else None,
            "outcome": "UNKNOWN",
            "elapsed_seconds": round(time.monotonic() - self.started_monotonic, 3),
        }
        intents.append(intent)
        persist(self.file, self.receipt)  # Consume the allowance before transmission.
        try:
            response = self.sender(method.upper(), url, headers, body)
            require(
                isinstance(response, HttpResponse)
                and type(response.status) is int
                and 100 <= response.status <= 599
                and len(response.body) <= MAX_RESPONSE_BYTES,
                "PILOT_RESPONSE_INVALID",
            )
        except Exception:
            intent["outcome"] = "UNKNOWN"
            persist(self.file, self.receipt)
            raise PilotBlocked("PILOT_HTTP_OUTCOME_UNKNOWN") from None
        intent["outcome"] = f"HTTP_{response.status}"
        if kind in {"claim", "heartbeat", "finish"}:
            valid_metadata = self._snapshot(kind, response)
            persist(self.file, self.receipt)
            require(valid_metadata, "PILOT_RESPONSE_INVALID")
        persist(self.file, self.receipt)
        return response


def worker_preflight(client: SupabaseRunnerClient) -> dict[str, object]:
    job_response = client._request("GET", JOB_PREFLIGHT_PATH, None)
    require(job_response.status == 200 and len(job_response.body) <= MAX_RESPONSE_BYTES,
            "PILOT_JOB_PREFLIGHT_FAILED")
    jobs = _unique_json(job_response.body)
    require(isinstance(jobs, list) and len(jobs) == 1 and isinstance(jobs[0], dict),
            "PILOT_JOB_SCOPE_BLOCKED")
    row = jobs[0]
    require(
        row.get("id") == JOB_ID
        and row.get("workspace_id") == WORKSPACE_ID
        and row.get("type") == JOB_TYPE
        and row.get("status") == "dispatched"
        and row.get("idempotency_key") == IDEMPOTENCY_KEY
        and row.get("payload_json") == PAYLOAD
        and type(row.get("max_attempts")) is int
        and row["max_attempts"] == 1
        and type(row.get("attempt_count")) is int
        and row["attempt_count"] == 0
        and row.get("runner_id") is None
        and row.get("lease_expires_at") is None
        and row.get("heartbeat_at") is None,
        "JOB_STATE_BLOCKED",
    )
    state_response = client._request("GET", STATE_PREFLIGHT_PATH, None)
    require(
        state_response.status == 200
        and len(state_response.body) <= MAX_RESPONSE_BYTES
        and _unique_json(state_response.body) == [],
        "PILOT_BROWSER_STATE_PRESENT",
    )
    return {"job_id": JOB_ID, "workspace_id": WORKSPACE_ID, "status": "dispatched"}


class PilotApiClient:
    """Explicitly delegates only claim, heartbeat, and finish."""

    __slots__ = ("_client",)

    def __init__(self, client: SupabaseRunnerClient):
        self._client = client

    def claim_job_run(self, job_id: str, runner_id: str):
        return self._client.claim_job_run(job_id, runner_id)

    def heartbeat_job(self, job_id: str, runner_id: str):
        return self._client.heartbeat_job(job_id, runner_id)

    def finish_job_run(
        self,
        run_id: str,
        runner_id: str,
        status: str,
        *,
        records_read: int,
        error_code: str | None,
        duration_ms: int = 0,
    ):
        return self._client.finish_job_run(
            run_id,
            runner_id,
            status,
            records_read=records_read,
            error_code=error_code,
            duration_ms=duration_ms,
        )


def remove_profile(profile: Path, run_dir: Path, base_dir: Path) -> bool:
    require(not profile.is_symlink(), "PILOT_PROFILE_BOUNDARY_BLOCKED")
    resolved_profile = profile.resolve()
    resolved_run = run_dir.resolve()
    resolved_base = base_dir.resolve()
    require(
        resolved_profile.parent == resolved_run
        and resolved_profile.is_relative_to(resolved_base)
        and resolved_run.is_relative_to(resolved_base),
        "PILOT_PROFILE_BOUNDARY_BLOCKED",
    )
    if resolved_profile.exists():
        shutil.rmtree(resolved_profile)
    return not resolved_profile.exists()


def _worker_environment(environment: dict[str, str]) -> dict[str, str]:
    keep = {
        "SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "APPDATA", "LOCALAPPDATA",
        "PROGRAMFILES", "PROGRAMFILES(X86)", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
        "HOME", "LANG", "LC_ALL", "GITHUB_ACTIONS", "GITHUB_REPOSITORY",
        "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_RUN_ATTEMPT", "GITHUB_RUN_ID",
        "GITHUB_SHA", APPROVAL, "JOB_ID", "JOB_TYPE", "SUPABASE_SECRET_KEY",
    }
    result = {key: value for key, value in environment.items() if key.upper() in keep}
    result.update(ANONYMIZED_TELEMETRY="false", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    return result


def _verify_worker(receipt: dict[str, object], exit_code: int) -> None:
    counts = receipt.get("counts")
    snapshots = receipt.get("server_snapshots")
    outcome = receipt.get("cli_outcome")
    intents = receipt.get("intents")
    require(
        exit_code == 0
        and isinstance(counts, dict)
        and all(type(counts.get(key)) is int for key in REQUEST_CAPS)
        and counts.get("job_preflight") == 1
        and counts.get("state_preflight") == 1
        and counts.get("claim") == 1
        and 20 <= counts.get("heartbeat", 0) <= 22
        and counts.get("finish") == 1
        and type(receipt.get("request_count")) is int
        and receipt.get("request_count") <= MAX_REQUESTS
        and isinstance(snapshots, list)
        and all(isinstance(item, dict) for item in snapshots)
        and len([item for item in snapshots if item.get("kind") == "claim"]) == 1
        and len([item for item in snapshots if item.get("kind") == "heartbeat"]) >= 20
        and receipt.get("finish_result") == "succeeded"
        and isinstance(outcome, dict)
        and receipt.get("status") == "WORKER_RETURNED"
        and outcome.get("status") == "succeeded"
        and type(outcome.get("records_read")) is int
        and outcome.get("records_read") == 0
        and type(outcome.get("duration_ms")) is int
        and outcome.get("duration_ms", 0) >= HOLD_SECONDS * 1000,
        "PILOT_WORKER_RESULT_UNCONFIRMED",
    )
    claims = [item for item in snapshots if item.get("kind") == "claim"]
    heartbeats = [item for item in snapshots if item.get("kind") == "heartbeat"]
    finishes = [item for item in snapshots if item.get("kind") == "finish"]
    claim = claims[0]
    require(
        len(finishes) == 1
        and _uuid(claim.get("run_id"))
        and claim.get("job_id") == JOB_ID
        and claim.get("workspace_id") == WORKSPACE_ID
        and claim.get("runner_id") == RUNNER_ID
        and type(claim.get("attempt")) is int
        and claim.get("attempt") == 1
        and _server_time(claim.get("lease_expires_at"))
        and all(
            item.get("job_id") == JOB_ID
            and item.get("run_id") == claim.get("run_id")
            and item.get("workspace_id") == WORKSPACE_ID
            and item.get("runner_id") == RUNNER_ID
            and _server_time(item.get("lease_expires_at"))
            for item in heartbeats
        )
        and finishes[0].get("run_id") == claim.get("run_id")
        and finishes[0].get("status") == "succeeded",
        "PILOT_SERVER_METADATA_MISMATCH",
    )
    require(isinstance(intents, list) and all(isinstance(item, dict) for item in intents),
            "PILOT_RECEIPT_INVALID")
    heartbeat_intents = [item for item in intents if item.get("kind") == "heartbeat"]
    require(
        heartbeat_intents
        and isinstance(heartbeat_intents[-1].get("elapsed_seconds"), (int, float))
        and type(heartbeat_intents[-1].get("elapsed_seconds")) is not bool
        and heartbeat_intents[-1].get("elapsed_seconds", 0) >= 600,
        "PILOT_HEARTBEAT_WINDOW_INCOMPLETE",
    )


def _worker(environment: dict[str, str], file: Path, chromium: str) -> dict[str, object]:
    head, run_id = context(environment)
    require(environment.get("GITHUB_ACTIONS") == "true", "PILOT_HOST_REQUIRED")
    require(Path(chromium).is_file(), "PILOT_CHROMIUM_REQUIRED")
    require(importlib.metadata.version("browser-use") == "0.13.6", "PILOT_SDK_CHANGED")
    receipt = json.loads(file.read_text(encoding="utf-8"))
    require(
        isinstance(receipt, dict)
        and receipt.get("status") == "WORKER_STARTED"
        and receipt.get("head") == head
        and receipt.get("run_id") == run_id
        and receipt.get("job_id") == JOB_ID,
        "PILOT_PREFLIGHT_REQUIRED",
    )
    require(
        cli_defaults_ok(),
        "PILOT_RUNNER_DEFAULTS_CHANGED",
    )
    secret_key = environment["SUPABASE_SECRET_KEY"]
    fake_state_key = base64.b64encode(os.urandom(32)).decode("ascii")
    runner_environment = {
        "AUTOMATION_ENABLED": "true",
        "MVP_LMS_WRITE_ENABLED": "false",
        "JOB_ID": JOB_ID,
        "RUNNER_ID": RUNNER_ID,
        "JOB_TYPE": JOB_TYPE,
        "SUPABASE_URL": BASE_URL,
        "SUPABASE_SECRET_KEY": secret_key,
        "BROWSER_STATE_ENCRYPTION_KEY": fake_state_key,
    }
    receipt["worker_started_monotonic"] = time.monotonic()
    persist(file, receipt)
    transport = WorkerApiTransport(receipt, file)
    client = transport.client(secret_key)
    worker_preflight(client)
    profile = file.parent / "profile"
    from browser_use.browser import BrowserSession
    from mindx_runner import cli

    session: BrowserSession | None = None

    def browser_factory(**options):
        nonlocal session
        session = BrowserSession(
            **options,
            is_local=True,
            use_cloud=False,
            executable_path=chromium,
            user_data_dir=str(profile),
            chromium_sandbox=os.environ.get("GITHUB_ACTIONS") != "true",
            args=[
                "--disable-background-networking", "--disable-component-update",
                "--disable-sync", "--no-first-run", "--disable-quic", "--no-pings",
                "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>",
                "--host-resolver-rules=MAP * ~NOTFOUND",
            ],
        )
        return session

    async def synthetic_adapter(config, claimed, browser) -> int:
        del config
        require(
            session is not None
            and browser._session is session
            and not browser._guard_failed
            and claimed.job_id == JOB_ID
            and claimed.workspace_id == WORKSPACE_ID
            and claimed.job_type == JOB_TYPE
            and claimed.payload == PAYLOAD
            and claimed.attempt == 1,
            "PILOT_CLAIM_SCOPE_BLOCKED",
        )
        targets = session.session_manager.get_all_targets()
        require(bool(targets), "PILOT_BLANK_BROWSER_REQUIRED")
        urls = [
            getattr(target, "url", None)
            for target in targets.values()
            if getattr(target, "target_type", "page") in {"page", "tab"}
        ]
        require(urls and all(url in {None, "", "about:blank", "chrome://newtab/"} for url in urls),
                "PILOT_BLANK_BROWSER_REQUIRED")
        receipt["browser_target_count"] = len(urls)
        receipt["adapter_started_monotonic"] = time.monotonic()
        persist(file, receipt)
        await asyncio.sleep(HOLD_SECONDS)
        receipt["adapter_completed_monotonic"] = time.monotonic()
        receipt["adapter_hold_seconds"] = (
            receipt["adapter_completed_monotonic"] - receipt["adapter_started_monotonic"]
        )
        persist(file, receipt)
        return 0

    try:
        import logging

        logging.disable(logging.CRITICAL)
        summary = asyncio.run(
            cli.run_job(
                JOB_ID,
                runner_environment,
                client_factory=lambda _: PilotApiClient(client),
                session_factory=browser_factory,
                adapter=synthetic_adapter,
            )
        )
        receipt["cli_outcome"] = {
            "status": summary.status,
            "records_read": summary.records_read,
            "duration_ms": int(
                (receipt.get("adapter_completed_monotonic", 0)
                 - receipt.get("adapter_started_monotonic", 0))
                * 1000
            ),
        }
        receipt["status"] = "WORKER_RETURNED"
    except Exception as error:
        error_code = cli.safe_error_code(error)
        receipt["cli_outcome"] = {"status": "UNKNOWN", "error_code": error_code}
        receipt["status"] = "WORKER_FAILED"
    finally:
        persist(file, receipt)
    return receipt


def cli_defaults_ok() -> bool:
    from mindx_runner import cli

    return cli.RUN_TIMEOUT_SECONDS == WALL_SECONDS and cli.HEARTBEAT_INTERVAL_SECONDS == HEARTBEAT_SECONDS


def _cleanup_owned(parent: dict[str, object], owned: dict[int, dict[str, object]]) -> tuple[list, list]:
    runtime_helpers.observe_children(parent, owned)
    for identity in list(owned.values()):
        runtime_helpers.observe_children(identity, owned)
    residual = [identity for identity in owned.values() if runtime_helpers.running(identity)]
    zombies = runtime_helpers.zombie_pids(owned)
    return residual, zombies


def _stop_owned_processes(
    parent: dict[str, object], owned: dict[int, dict[str, object]], process
) -> tuple[list, list]:
    """Stop only descendants previously identified by PID and creation time."""
    runtime_helpers.observe_children(parent, owned)
    if process is not None and process.poll() is None:
        require(runtime_helpers.running(parent) is not None, "PILOT_WORKER_IDENTITY_UNKNOWN")
        process.kill()
        process.wait(timeout=5)
    for identity in reversed(list(owned.values())):
        child = runtime_helpers.running(identity)
        if child is not None:
            child.kill()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        residual = [identity for identity in owned.values() if runtime_helpers.running(identity)]
        if not residual:
            break
        time.sleep(0.1)
    return _cleanup_owned(parent, owned)


def supervise(environment: dict[str, str], file: Path, chromium: str) -> dict[str, object]:
    head, run_id = context(environment)
    require(Path(chromium).is_file(), "PILOT_CHROMIUM_REQUIRED")
    require(importlib.metadata.version("browser-use") == "0.13.6", "PILOT_SDK_CHANGED")
    folder = file.parent
    profile = folder / "profile"
    require(not profile.exists(), "PILOT_PROFILE_PREEXISTS")
    receipt = consume_preflight(environment, file)
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--receipt", str(file), "--chromium", chromium]
    env = _worker_environment(environment)
    started = time.monotonic()
    process = None
    owned: dict[int, dict[str, object]] = {}
    parent: dict[str, object] | None = None
    killed = False
    profile_owned = False
    worker_error: str | None = None
    worker_verified = False
    verified_worker_receipt: dict[str, object] | None = None
    final_receipt: dict[str, object] | None = None
    try:
        process = subprocess.Popen(
            command,
            env=env,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name == "posix",
        )
        profile_owned = True
        import psutil

        parent = {"pid": process.pid, "created": psutil.Process(process.pid).create_time()}
        while process.poll() is None:
            runtime_helpers.observe_children(parent, owned)
            if time.monotonic() - started > WALL_SECONDS:
                require(runtime_helpers.running(parent) is not None, "PILOT_WORKER_IDENTITY_UNKNOWN")
                process.kill()
                killed = True
                break
            time.sleep(0.1)
        process.wait(timeout=5)
        require(not killed, "PILOT_WORKER_WALL_EXCEEDED")
        worker_receipt = json.loads(file.read_text(encoding="utf-8"))
        require(isinstance(worker_receipt, dict), "PILOT_RECEIPT_INVALID")
        worker_receipt["worker_exit_code"] = process.returncode
        worker_receipt["worker_killed"] = killed
        worker_receipt["owned_processes"] = list(owned.values())
        worker_receipt["wall_elapsed_seconds"] = time.monotonic() - started
        persist(file, worker_receipt)
        _verify_worker(worker_receipt, process.returncode)
        verified_worker_receipt = worker_receipt
        worker_verified = True
    except PilotBlocked as error:
        worker_error = str(error)
    except Exception:
        worker_error = "PILOT_WORKER_UNKNOWN"
    finally:
        cleanup_error = None
        profile_error = None
        residual = []
        zombies = []
        if process is not None and parent is None:
            cleanup_error = "PILOT_CLEANUP_UNCONFIRMED"
            residual = list(owned.values())
        elif parent is not None:
            try:
                residual, zombies = _stop_owned_processes(parent, owned, process)
                if residual or zombies:
                    cleanup_error = "PILOT_CLEANUP_UNCONFIRMED"
            except Exception:
                cleanup_error = "PILOT_CLEANUP_UNCONFIRMED"
                residual = list(owned.values())
                zombies = []

        if verified_worker_receipt is not None:
            final_receipt = dict(verified_worker_receipt)
        else:
            try:
                persisted = json.loads(file.read_text(encoding="utf-8"))
                if isinstance(persisted, dict):
                    final_receipt = persisted
                else:
                    final_receipt = dict(receipt)
                    worker_error = worker_error or "PILOT_RECEIPT_INVALID"
            except Exception:
                final_receipt = dict(receipt)
                worker_error = worker_error or "PILOT_RECEIPT_INVALID"
        final_receipt["worker_exit_code"] = process.returncode if process is not None else None
        final_receipt["worker_killed"] = killed
        final_receipt["owned_processes"] = list(owned.values())
        final_receipt["residual_processes"] = residual
        final_receipt["zombie_pids"] = zombies
        final_receipt["wall_elapsed_seconds"] = time.monotonic() - started

        if profile_owned:
            if cleanup_error is None:
                try:
                    final_receipt["owned_profile_removed"] = remove_profile(
                        profile, folder, folder
                    )
                except Exception:
                    final_receipt["owned_profile_removed"] = False
            else:
                final_receipt["owned_profile_removed"] = False
            if final_receipt.get("owned_profile_removed") is not True:
                profile_error = "PILOT_PROFILE_CLEANUP_FAILED"

        failure = cleanup_error or profile_error or worker_error
        if failure is None and worker_verified and verified_worker_receipt is not None:
            final_receipt["status"] = "PASS"
            final_receipt.pop("error_code", None)
        else:
            final_receipt["status"] = "BLOCKED"
            final_receipt["error_code"] = failure or "PILOT_WORKER_RESULT_UNCONFIRMED"
        persist(file, final_receipt)
    assert final_receipt is not None
    return final_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--run", action="store_true")
    modes.add_argument("--worker", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--chromium")
    args = parser.parse_args(argv)
    try:
        file = args.receipt.resolve()
        if args.preflight:
            result = preflight(dict(os.environ), file)
            print(json.dumps({"status": result["status"], "error_code": result.get("error_code")}))
            return 0 if result["status"] == "PREFLIGHT_PASS" else 1
        if args.worker:
            result = _worker(dict(os.environ), file, args.chromium or "")
            print(json.dumps({"status": result["status"], "error_code": result.get("error_code")}))
            return 0 if result["status"] == "WORKER_RETURNED" else 1
        require(args.chromium is not None, "PILOT_CHROMIUM_REQUIRED")
        result = supervise(dict(os.environ), file, args.chromium)
        print(json.dumps({"status": result["status"], "error_code": result.get("error_code")}))
        return 0 if result["status"] == "PASS" else 1
    except PilotBlocked as error:
        print(json.dumps({"status": "BLOCKED", "error_code": str(error)}))
        return 1
    except Exception:
        print('{"status":"BLOCKED","error_code":"PILOT_UNKNOWN"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
