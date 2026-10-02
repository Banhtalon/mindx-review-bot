import re
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[4] / ".github" / "workflows" / "browser-runner.yml"
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
    teaching_preflight = WORKFLOW.split("name: Preflight Teaching", 1)[1].split(
        "name: Preflight LMS", 1
    )[0]
    lms_preflight = WORKFLOW.split("name: Preflight LMS", 1)[1].split(
        "name: Install Chromium", 1
    )[0]
    teaching_block = WORKFLOW.split("name: Execute Teaching", 1)[1].split(
        "name: Execute LMS", 1
    )[0]
    lms_block = WORKFLOW.split("name: Execute LMS", 1)[1]

    assert set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", teaching_block)) == {
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "BROWSER_STATE_ENCRYPTION_KEY",
        "MINDX_TEACHING_TARGET_JSON",
        "TEACHING_USERNAME",
        "TEACHING_PASSWORD",
    }
    assert set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", lms_block)) == {
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "BROWSER_STATE_ENCRYPTION_KEY",
    }
    assert "MVP_LMS_WRITE_ENABLED: false" in teaching_block
    assert "MVP_LMS_WRITE_ENABLED: false" in lms_block
    assert "MINDX_SITE_ADAPTER: ${{ vars.MINDX_SITE_ADAPTER }}" in teaching_block
    assert "MINDX_SITE_ADAPTER: ${{ vars.MINDX_SITE_ADAPTER }}" in lms_block
    assert set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", teaching_preflight)) == {
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "BROWSER_STATE_ENCRYPTION_KEY",
        "MINDX_TEACHING_TARGET_JSON",
    }
    assert set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", lms_preflight)) == {
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "BROWSER_STATE_ENCRYPTION_KEY",
    }
    assert "MINDX_SITE_ADAPTER: ${{ vars.MINDX_SITE_ADAPTER }}" in teaching_preflight
    assert "MINDX_SITE_ADAPTER: ${{ vars.MINDX_SITE_ADAPTER }}" in lms_preflight
    assert "if: inputs.job_type == 'sync_teaching'" in teaching_block
    assert "if: inputs.job_type == 'read_lms_pending'" in lms_block


def test_live_workflow_does_not_upload_artifacts_or_enable_browser_recording() -> None:
    assert "upload-artifact" not in WORKFLOW
    assert "record_video" not in WORKFLOW
    assert "traces_dir" not in WORKFLOW
    assert "screenshot" not in WORKFLOW.lower()


def test_live_workflow_uses_locked_project_and_safe_runner_command() -> None:
    assert "uv sync --locked --project apps/browser-runner" in WORKFLOW
    assert WORKFLOW.index("name: Install Chromium") > WORKFLOW.index("name: Preflight LMS")
    assert 'uv run --project apps/browser-runner mindx-runner run "$JOB_ID"' in WORKFLOW
