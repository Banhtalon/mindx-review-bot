import re
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[4] / ".github" / "workflows" / "browser-runner.yml"
).read_text(encoding="utf-8")
HOSTED_WORKFLOW = (
    Path(__file__).resolve().parents[4]
    / ".github"
    / "workflows"
    / "phase2-hosted-verify.yml"
).read_text(encoding="utf-8")
HOSTED_PROBE_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "mindx_runner" / "hosted_probe.py"
).read_text(encoding="utf-8")


def test_live_workflow_is_manual_and_uses_minimal_permissions() -> None:
    assert "workflow_dispatch:" in WORKFLOW
    assert "permissions:\n  contents: read" in WORKFLOW
    assert "timeout-minutes: 15" in WORKFLOW
    assert "cancel-in-progress: false" in WORKFLOW


def test_live_workflow_pins_third_party_actions_to_full_commit_shas() -> None:
    action_refs = re.findall(r"uses:\s+([^\s#]+)", WORKFLOW)

    assert action_refs
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", ref) for ref in action_refs)


def test_live_workflow_scopes_credentials_by_job_type() -> None:
    teaching_block = WORKFLOW.split("name: Execute Teaching", 1)[1].split(
        "name: Execute LMS", 1
    )[0]
    lms_block = WORKFLOW.split("name: Execute LMS", 1)[1]

    assert set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", teaching_block)) == {
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "TEACHING_USERNAME",
        "TEACHING_PASSWORD",
        "BROWSER_STATE_ENCRYPTION_KEY",
    }
    assert set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", lms_block)) == {
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "LMS_USERNAME",
        "LMS_PASSWORD",
        "BROWSER_STATE_ENCRYPTION_KEY",
    }
    assert "MVP_LMS_WRITE_ENABLED: false" in teaching_block
    assert "MVP_LMS_WRITE_ENABLED: false" in lms_block
    assert "if: inputs.job_type == 'sync_teaching'" in teaching_block
    assert "if: inputs.job_type == 'read_lms_pending'" in lms_block


def test_live_workflow_does_not_upload_artifacts_or_enable_browser_recording() -> None:
    assert "upload-artifact" not in WORKFLOW
    assert "record_video" not in WORKFLOW
    assert "traces_dir" not in WORKFLOW
    assert "screenshot" not in WORKFLOW.lower()


def test_live_workflow_uses_locked_project_and_safe_runner_command() -> None:
    assert "uv sync --locked --project apps/browser-runner" in WORKFLOW
    assert 'uv run --project apps/browser-runner mindx-runner run "$JOB_ID"' in WORKFLOW


def test_hosted_probe_is_manual_only_bounded_and_pinned() -> None:
    assert "workflow_dispatch:" in HOSTED_WORKFLOW
    assert "schedule:" not in HOSTED_WORKFLOW
    assert "pull_request_target:" not in HOSTED_WORKFLOW
    assert "permissions:\n  contents: read" in HOSTED_WORKFLOW
    assert "timeout-minutes: 15" in HOSTED_WORKFLOW
    assert "inputs.probe_id" in HOSTED_WORKFLOW
    refs = re.findall(r"uses:\s+([^\s#]+)", HOSTED_WORKFLOW)
    assert refs
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", ref) for ref in refs)


def test_hosted_probe_separates_persist_reuse_and_always_cleanup() -> None:
    assert "database:" in HOSTED_WORKFLOW
    assert "state_persist:" in HOSTED_WORKFLOW
    assert "state_reuse_reset:" in HOSTED_WORKFLOW
    assert "cleanup:" in HOSTED_WORKFLOW
    assert "if: always()" in HOSTED_WORKFLOW
    assert "phase2-hosted-probe database" in HOSTED_WORKFLOW
    assert "phase2-hosted-probe state-persist" in HOSTED_WORKFLOW
    assert "phase2-hosted-probe state-reuse-reset" in HOSTED_WORKFLOW
    assert "phase2-hosted-probe cleanup" in HOSTED_WORKFLOW


def test_hosted_probe_never_installs_or_opens_a_browser_or_uploads_artifacts() -> None:
    lowered = HOSTED_WORKFLOW.lower()
    assert "mindx-runner run" not in HOSTED_WORKFLOW
    assert "browser-use install" not in HOSTED_WORKFLOW
    assert "upload-artifact" not in lowered
    assert "screenshot" not in lowered
    assert "trace" not in lowered
    assert "record_video" not in lowered
    assert "browser_driver" not in HOSTED_PROBE_SOURCE
    assert "ReadonlyBrowserSession" not in HOSTED_PROBE_SOURCE
