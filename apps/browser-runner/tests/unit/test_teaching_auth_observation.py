import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_live_adapter import _TARGET_ENV as ENVIRONMENT
from test_live_adapter import CONFIG, TEACHING_HTML, FakeBrowser, FakePage, claimed

from mindx_runner import cli
from mindx_runner.live_adapter import readonly_site_adapter
from mindx_runner.safe_logging import sanitize_log_metadata

LOGIN_HTML = (
    '<form method="POST"><input name="username"><input type="password" name="password"></form>'
)
PAYLOAD = {
    "teaching_url": "https://teachingmindx.top/",
    "allowed_class_codes": ["SYN-ROBOTICS-01"],
    "expected_class_code": "SYN-ROBOTICS-01",
    "expected_session_number": 3,
}


class LoginBrowser(FakeBrowser):
    login_calls = 0
    login_fails = False

    async def login_teaching(self, page: FakePage, username: str, password: str) -> None:
        self.login_calls += 1
        if self.login_fails:
            raise RuntimeError("AUTH_FAILED")
        page.html = TEACHING_HTML


@pytest.mark.asyncio
@pytest.mark.parametrize("login", [False, True])
async def test_auth_observation_requires_successful_validated_read(login: bool) -> None:
    browser = LoginBrowser(FakePage(LOGIN_HTML if login else TEACHING_HTML))
    assert await readonly_site_adapter(CONFIG, claimed(PAYLOAD), browser) == 1
    assert getattr(browser, "teaching_auth_mode", None) == (
        "password_login" if login else "saved_session"
    )
    assert browser.login_calls == int(login)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["failed", "mismatch", "zero", "challenge", "missing"])
async def test_failed_mismatched_or_empty_read_cannot_retain_auth_claim(outcome: str) -> None:
    browser = LoginBrowser(FakePage(LOGIN_HTML if outcome != "zero" else TEACHING_HTML))
    browser.teaching_auth_mode = "saved_session"
    browser.login_fails = outcome == "failed"
    if outcome == "challenge":
        browser.page.html += '<input name="otp" autocomplete="one-time-code">'
    config = replace(CONFIG, teaching_password="") if outcome == "missing" else CONFIG
    payload = dict(PAYLOAD)
    if outcome == "mismatch":
        payload["expected_session_number"] = 99
    if outcome == "zero":
        payload = {"teaching_url": PAYLOAD["teaching_url"], "allowed_class_codes": ["OTHER"]}
        with pytest.raises(cli.RunnerError, match="^TEACHING_DATA_INVALID$"):
            await readonly_site_adapter(config, claimed(payload), browser)
    else:
        with pytest.raises(cli.RunnerError):
            await readonly_site_adapter(config, claimed(payload), browser)
    assert getattr(browser, "teaching_auth_mode", None) is None


@pytest.mark.parametrize("mode", ["saved_session", "password_login", "not_observed"])
def test_only_closed_auth_enum_is_allowed_in_metadata(mode: str) -> None:
    assert sanitize_log_metadata({"teaching_auth_mode": mode}) == {"teaching_auth_mode": mode}
    assert sanitize_log_metadata({"teaching_auth_mode": mode + "\nprivate-value"}) == {}


@pytest.mark.parametrize(("login", "finish_fails"), [(False, False), (True, False), (True, True)])
def test_cli_carries_real_adapter_observation_after_finalization(
    login: bool, finish_fails: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    browser = LoginBrowser(FakePage(LOGIN_HTML if login else TEACHING_HTML))
    finished = []

    class Client:
        def claim_job_run(self, *_: object) -> object:
            return claimed(PAYLOAD)

        def heartbeat_job(self, *_: object) -> None:
            pass

        def finish_job_run(self, *args: object, **kwargs: object) -> None:
            finished.append((args, kwargs))
            if finish_fails:
                raise cli.RunnerError("SUPABASE_UNAVAILABLE")

    async def no_browser_io(*_: object, **__: object) -> dict[str, object]:
        return {}

    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("TEACHING_USERNAME", "synthetic-observer@example.invalid")
    monkeypatch.setenv("TEACHING_PASSWORD", "only-synthetic-login-value")
    report = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(report))
    monkeypatch.setattr(cli, "SupabaseRunnerClient", lambda *_: Client())
    monkeypatch.setattr(cli, "ReadonlyBrowserSession", lambda **_: browser)
    monkeypatch.setattr(cli, "_load_browser_storage_state", no_browser_io)
    monkeypatch.setattr(cli, "_start_browser_with_bound", no_browser_io)
    monkeypatch.setattr(cli, "_close_browser_with_bound", no_browser_io)
    monkeypatch.setattr(cli, "load_configured_adapter", lambda _: readonly_site_adapter)
    assert cli.main(["run", ENVIRONMENT["JOB_ID"]]) == int(finish_fails)
    data = json.loads(capsys.readouterr().out)
    if finish_fails:
        assert data == {"status": "failed", "error_code": "SUPABASE_UNAVAILABLE"}
        assert not report.exists() and len(finished) == 1
        return
    assert data["teaching_auth_mode"] == ("password_login" if login else "saved_session")
    assert data["records_read"] == 1
    assert len(finished) == 1 and finished[0][0][2] == "succeeded"
    assert "only-synthetic-login-value" not in report.read_text(encoding="utf-8")
    assert "synthetic-observer@example.invalid" not in report.read_text(encoding="utf-8")
    assert ("mật khẩu" if login else "phiên") in report.read_text(encoding="utf-8")


@pytest.mark.parametrize("mode", [None, "untrusted-private-value", {"nested": "private-value"}])
def test_unobserved_or_invalid_mode_never_leaks_or_infers_authentication(
    mode: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = SimpleNamespace(
        job_id=ENVIRONMENT["JOB_ID"], status="succeeded", records_read=1, teaching_auth_mode=mode
    )

    async def run(*_: object, **__: object) -> object:
        return result

    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setattr(cli, "run_job", run)
    monkeypatch.setattr(cli, "load_configured_adapter", lambda _: readonly_site_adapter)
    assert cli.main(["run", ENVIRONMENT["JOB_ID"]]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["teaching_auth_mode"] == "not_observed"
    assert "private-value" not in output


def test_optional_summary_write_failure_does_not_fail_finished_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def run(*_: object, **__: object) -> object:
        return SimpleNamespace(
            job_id=ENVIRONMENT["JOB_ID"], status="succeeded", records_read=1,
            teaching_auth_mode="saved_session",
        )

    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "missing" / "summary.md"))
    monkeypatch.setattr(cli, "run_job", run)
    monkeypatch.setattr(cli, "load_configured_adapter", lambda _: readonly_site_adapter)
    assert cli.main(["run", ENVIRONMENT["JOB_ID"]]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "succeeded"


def test_lms_summary_cannot_claim_teaching_authentication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "summary.md"
    cli._report_success(
        cli.SafeRunSummary(
            ENVIRONMENT["JOB_ID"], "00000000-0000-4000-8000-000000000002", "succeeded", 1,
            teaching_auth_mode="password_login",
        ),
        {"GITHUB_STEP_SUMMARY": str(report)}, "read_lms_pending",
    )
    assert "teaching_auth_mode" not in json.loads(capsys.readouterr().out)
    assert not report.exists()


def test_zero_count_cannot_claim_successful_password_login(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "summary.md"
    cli._report_success(
        cli.SafeRunSummary(
            ENVIRONMENT["JOB_ID"], "00000000-0000-4000-8000-000000000002", "succeeded", 0,
            teaching_auth_mode="password_login",
        ),
        {"GITHUB_STEP_SUMMARY": str(report)}, "sync_teaching",
    )
    assert json.loads(capsys.readouterr().out)["teaching_auth_mode"] == "not_observed"
    assert "Chưa có bằng chứng" in report.read_text(encoding="utf-8")
