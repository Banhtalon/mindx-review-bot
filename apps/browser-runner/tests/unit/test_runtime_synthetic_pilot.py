"""Synthetic guards only. No cloud request, worker launch or browser in these tests."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    "runtime_pilot", ROOT / "scripts/runtime_synthetic_pilot.py"
)
assert SPEC is not None and SPEC.loader is not None
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def environment():
    return {
        "GITHUB_REPOSITORY": "Banhtalon/mindx-review-bot",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_NUMBER": "1",
        "GITHUB_RUN_ID": "10",
        "GITHUB_SHA": "a" * 40,
        pilot.APPROVAL: "a" * 40,
        "GITHUB_TOKEN": "public-synthetic-test-value",
    }


def history(**changes):
    run = {
        "id": 10,
        "head_sha": "a" * 40,
        "head_branch": "main",
        "event": "workflow_dispatch",
        "run_attempt": 1,
        "run_number": 1,
    }
    run.update(changes)
    return json.dumps({"total_count": 1, "workflow_runs": [run]}).encode()


def test_first_dispatch_consumes_preflight_and_cannot_replay(tmp_path):
    file, env = tmp_path / "receipt.json", environment()
    transport = Mock(return_value=history())
    assert pilot.preflight(env, file, transport)["status"] == "PREFLIGHT_PASS"
    assert transport.call_count == 1
    assert pilot.preflight(env, file, transport)["error_code"] == "RUNTIME_ALREADY_ATTEMPTED"
    assert transport.call_count == 1
    env.pop("GITHUB_TOKEN")
    assert pilot.consume_preflight(env, file)["status"] == "RUNTIME_STARTED"
    with pytest.raises(pilot.PilotBlocked, match="RUNTIME_PREFLIGHT_REQUIRED"):
        pilot.consume_preflight(env, file)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (pilot.APPROVAL, "b" * 40),
        ("GITHUB_REPOSITORY", "other/repo"),
        ("GITHUB_EVENT_NAME", "push"),
        ("GITHUB_REF", "refs/heads/other"),
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("GITHUB_RUN_NUMBER", "2"),
        ("GITHUB_RUN_ID", "0"),
        ("GITHUB_RUN_ID", "10\n"),
        ("SUPABASE_SECRET_KEY", "public-synthetic-test-value"),
        ("TEACHING_PASSWORD", "public-synthetic-test-value"),
    ],
)
def test_context_blocks_before_any_request(tmp_path, key, value):
    env = {**environment(), key: value}
    transport = Mock(return_value=history())
    result = pilot.preflight(env, tmp_path / "receipt.json", transport)
    assert result["status"] == "BLOCKED"
    assert result["github_reads"] == 0
    transport.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        b"not-json",
        b"[]",
        b"{}",
        b'{"total_count":0,"workflow_runs":[]}',
        b'{"total_count":101,"workflow_runs":[]}',
        b'{"total_count":true,"workflow_runs":[]}',
        history(id=9),
        history(id=10.0),
        history(head_sha="b" * 40),
        history(head_branch="other"),
        history(run_attempt=2),
        history(run_number=2),
        history(run_attempt=True),
        history(event="push"),
        json.dumps(
            {"total_count": 2, "workflow_runs": json.loads(history())["workflow_runs"]}
        ).encode(),
    ],
)
def test_incomplete_or_prior_history_consumes_read_but_blocks(tmp_path, raw):
    file, transport = tmp_path / "receipt.json", Mock(return_value=raw)
    result = pilot.preflight(environment(), file, transport)
    assert result["status"] == "BLOCKED" and result["github_reads"] == 1
    assert transport.call_count == 1
    assert pilot.preflight(environment(), file, transport)["status"] == "BLOCKED"
    assert transport.call_count == 1


def test_unknown_http_failure_never_leaks_or_retries(tmp_path):
    transport = Mock(side_effect=OSError("private-error-text-must-not-appear"))
    result = pilot.preflight(environment(), tmp_path / "receipt.json", transport)
    assert result["status"] == "BLOCKED" and result["github_reads"] == 1
    assert "private-error-text" not in json.dumps(result)
    assert transport.call_count == 1


def test_token_or_other_run_cannot_consume_pass(tmp_path):
    file, env = tmp_path / "receipt.json", environment()
    assert pilot.preflight(env, file, lambda _: history())["status"] == "PREFLIGHT_PASS"
    with pytest.raises(pilot.PilotBlocked, match="RUNTIME_TOKEN_SCOPE_BLOCKED"):
        pilot.consume_preflight(env, file)
    env.pop("GITHUB_TOKEN")
    env["GITHUB_RUN_ID"] = "11"
    with pytest.raises(pilot.PilotBlocked, match="RUNTIME_PREFLIGHT_REQUIRED"):
        pilot.consume_preflight(env, file)


def test_owned_identity_denies_unknown_access_and_recycled_pid():
    identity = {"pid": 12345, "created": 100.0}
    with patch.object(pilot.psutil, "Process", side_effect=psutil.NoSuchProcess(12345)):
        assert pilot.running(identity) is None
    with patch.object(pilot.psutil, "Process", side_effect=psutil.AccessDenied(12345)):
        with pytest.raises(psutil.AccessDenied):
            pilot.running(identity)
    with patch.object(pilot.psutil, "Process") as process:
        process.return_value.create_time.return_value = 101.0
        process.return_value.is_running.return_value = True
        assert pilot.running(identity) is None
        process.return_value.create_time.return_value = 100.0
        process.return_value.status.return_value = psutil.STATUS_ZOMBIE
        assert pilot.running(identity) is None
        assert pilot.zombie_pids({12345: identity}) == [12345]
        process.return_value.status.return_value = psutil.STATUS_RUNNING
        assert pilot.running(identity) is process.return_value


def events(case):
    result = [
        {"event": "worker_started", "seconds": 0, "wall_seconds": 720, "heartbeat_seconds": 30},
        {"event": "claim", "seconds": 1},
        {"event": "browser_ready", "seconds": 2, "target_count": 1},
    ]
    if case == "hard_stop":
        return result
    result += [{"event": "heartbeat", "seconds": t} for t in range(32, 650, 30)]
    if case == "success":
        result.append({"event": "adapter_done", "seconds": 652})
        status, error, seconds = "succeeded", None, 652
    else:
        result.append({"event": "adapter_cancelled", "seconds": 718})
        status, error, seconds = "failed", "RUNNER_TIMEOUT", 718
    result += [
        {
            "event": "finish",
            "seconds": seconds,
            "status": status,
            "error_code": error,
            "records": 0,
        },
        {"event": "worker_result", "seconds": seconds + 0.1, "status": status, "error_code": error},
        {"event": "worker_returned", "seconds": seconds + 0.2},
    ]
    return result


@pytest.mark.parametrize("case", pilot.CASES)
def test_cloud_case_acceptance_requires_default_natural_receipt(case):
    pilot.verify_case(
        case, events(case), int(case == "hard_stop"), case == "hard_stop", [], False, 720
    )


@pytest.mark.parametrize(
    "mutation", ["early_timeout", "records", "duplicate_finish", "residual", "missing_heartbeat"]
)
def test_forged_timeout_or_dirty_cleanup_cannot_pass(mutation):
    data, residual = events("timeout"), []
    if mutation == "early_timeout":
        next(e for e in data if e["event"] == "adapter_cancelled")["seconds"] = 33
    if mutation == "records":
        next(e for e in data if e["event"] == "finish")["records"] = 1
    if mutation == "duplicate_finish":
        data.append(next(e for e in data if e["event"] == "finish"))
    if mutation == "residual":
        residual = [{"pid": 1}]
    if mutation == "missing_heartbeat":
        data = [e for e in data if e["event"] != "heartbeat"]
    with pytest.raises(pilot.PilotBlocked):
        pilot.verify_case("timeout", data, 0, False, residual, False, 720)


def test_short_success_or_claimed_finally_after_hardkill_rejected():
    data = events("success")
    next(e for e in data if e["event"] == "adapter_done")["seconds"] = 37
    with pytest.raises(pilot.PilotBlocked):
        pilot.verify_case("success", data, 0, False, [], False, 38)
    with pytest.raises(pilot.PilotBlocked):
        pilot.verify_case(
            "hard_stop",
            events("hard_stop")
            + [
                {"event": "worker_returned", "seconds": 5},
            ],
            1,
            True,
            [],
            False,
            6,
        )


def test_launcher_failure_retains_failed_receipt_without_browser(tmp_path):
    with patch.object(pilot.subprocess, "Popen", side_effect=OSError("private-detail")):
        result = pilot.supervise("success", tmp_path, "unused-synthetic-path", True)
    assert result["status"] == "FAILED"
    assert "private-detail" not in json.dumps(result)
    assert json.loads((tmp_path / "success/receipt.json").read_text()) == result


def test_workflow_is_disabled_manual_readonly_and_token_is_preflight_only():
    raw = (ROOT / ".github/workflows/runtime-synthetic-pilot.yml").read_text()
    assert "workflow_dispatch:" in raw and "schedule:" not in raw
    assert "push:" not in raw and "pull_request:" not in raw and "secrets." not in raw
    assert "github.run_number == 1" in raw and "github.run_attempt == 1" in raw
    assert "contents: read" in raw and "actions: read" in raw
    assert "timeout-minutes: 40" in raw and "runs-on: ubuntu-24.04" in raw
    runtime_step = raw.split("- name: Run three real processes", 1)[1]
    assert "GITHUB_TOKEN:" not in runtime_step
    assert "--cloud" in runtime_step and "--smoke" not in runtime_step
