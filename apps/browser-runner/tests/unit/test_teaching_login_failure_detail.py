import json
from pathlib import Path

import pytest
from test_browser_driver import FakeCdp, FakePage
from test_cli import ENVIRONMENT as RUN_ENVIRONMENT
from test_cli import JOB_ID, RUN_ID, FakeClient, FakeSession
from test_live_adapter import _TARGET_ENV as ENVIRONMENT
from test_live_adapter import CONFIG, FakeBrowser, claimed
from test_live_adapter import FakePage as ContentPage
from test_teaching_auth import PASSWORD, USER, event
from test_teaching_auth_observation import LOGIN_HTML, PAYLOAD, TEACHING_HTML
from test_teaching_auth_observation import LoginBrowser as SuccessfulLoginBrowser

from mindx_runner import browser_driver, cli
from mindx_runner.browser_driver import ReadonlyBrowserSession
from mindx_runner.live_adapter import readonly_site_adapter
from mindx_runner.safe_logging import sanitize_log_metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("case,expected", [
    ("script", "script_failed"),
    ("absent", "request_not_observed"),
    ("body", "request_body_unavailable"),
    ("rejected", "request_rejected"),
    ("send", "request_send_failed"),
    ("timeout", "wait_timeout"),
])
async def test_driver_records_safe_failure_without_relaxing_post_guard(
    case: str, expected: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = ReadonlyBrowserSession()
    cdp = FakeCdp()
    browser._guard_cdp = cdp
    if case == "send":
        async def fail_send(**_: object) -> None:
            raise ValueError("synthetic-private-value")
        monkeypatch.setattr(cdp.fetch_send, "continueRequest", fail_send)
    if case == "timeout":
        original = browser_driver.asyncio.timeout
        monkeypatch.setattr(browser_driver.asyncio, "timeout", lambda _: original(0.01))

    class LoginPage(FakePage):
        async def evaluate(self, script: str, *args: str) -> str:
            if args:
                if case == "script":
                    raise ValueError("synthetic-private-value")
                if case != "absent":
                    request = event()
                    if case == "body":
                        request["request"].pop("postData")
                    if case == "rejected":
                        request["request"]["postData"] += "&unexpected=synthetic"
                    await browser._handle_request_paused(request, self.session_id)
                return "LOGIN_SENT"
            if case == "timeout":
                return "WAITING"
            if case == "send":
                raise ValueError("synthetic-private-value")
            return "COMPLETE"

    # A transport error is then surfaced by evaluation; no extra POST is submitted.
    if case == "send":
        original_timeout = browser_driver.asyncio.timeout
        monkeypatch.setattr(browser_driver.asyncio, "timeout", lambda _: original_timeout(0.01))
    try:
        with pytest.raises(RuntimeError, match="^AUTH_FAILED$"):
            await browser.login_teaching(LoginPage(), USER, PASSWORD)
        assert browser.teaching_login_failure == expected
        assert browser._teaching_login_pending is None
        assert len(cdp.fetch_send.continued) <= 1
        if case in {"body", "rejected", "send"}:
            assert cdp.fetch_send.failed
    finally:
        await browser.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("case,expected", [
    ("driver", "request_rejected"),
    ("page", "post_login_page_failed"),
    ("still_login", "post_login_still_login"),
])
async def test_adapter_carries_failure_and_clears_stale_metadata(case: str, expected: str) -> None:
    class LoginBrowser(FakeBrowser):
        teaching_login_failure = "script_failed"
        login_calls = 0

        async def login_teaching(self, *_: object) -> None:
            assert self.teaching_login_failure is None
            self.login_calls += 1
            if case == "driver":
                self.teaching_login_failure = "request_rejected"
                raise RuntimeError("AUTH_FAILED")

        async def open(self, url: str) -> ContentPage:
            if self.login_calls and case == "page":
                raise ValueError("synthetic-private-value")
            return await super().open(url)

    browser = LoginBrowser(ContentPage(LOGIN_HTML))
    with pytest.raises(cli.RunnerError, match="^AUTH_FAILED$") as error:
        await readonly_site_adapter(CONFIG, claimed(PAYLOAD), browser)
    assert error.value.teaching_login_failure == expected
    assert browser.login_calls == 1
    assert getattr(browser, "teaching_auth_mode", None) is None


@pytest.mark.parametrize("detail", [
    "script_failed", "request_not_observed", "request_body_unavailable", "request_rejected",
    "request_send_failed", "wait_timeout", "post_login_page_failed", "post_login_still_login",
    None, "synthetic-private-value", {"nested": "synthetic-private-value"},
])
def test_cli_failure_json_and_summary_are_closed_and_do_not_claim_success(
    detail: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = cli.RunnerError("AUTH_FAILED")
    error.teaching_login_failure = detail

    async def run(*_: object, **__: object) -> object:
        raise error

    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    report = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(report))
    monkeypatch.setattr(cli, "run_job", run)
    monkeypatch.setattr(cli, "load_configured_adapter", lambda _: readonly_site_adapter)
    assert cli.main(["run", ENVIRONMENT["JOB_ID"]]) == 1
    output = capsys.readouterr().out
    expected = sanitize_log_metadata({"teaching_login_failure": detail}).get(
        "teaching_login_failure", "not_observed",
    )
    assert json.loads(output) == {
        "status": "failed", "error_code": "AUTH_FAILED", "teaching_login_failure": expected,
    }
    text = report.read_text(encoding="utf-8")
    assert "Đăng nhập chưa thành công" in text and "0" in text
    assert "synthetic-private-value" not in output + text
    assert "password_login" not in output + text


def test_summary_write_failure_and_lms_cannot_add_teaching_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    async def run(*_: object, **__: object) -> object:
        raise cli.RunnerError("AUTH_FAILED", teaching_login_failure="request_rejected")

    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "missing" / "summary.md"))
    monkeypatch.setattr(cli, "run_job", run)
    monkeypatch.setattr(cli, "load_configured_adapter", lambda _: readonly_site_adapter)
    assert cli.main(["run", ENVIRONMENT["JOB_ID"]]) == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "AUTH_FAILED"
    monkeypatch.setenv("JOB_TYPE", "read_lms_pending")
    assert cli.main(["run", ENVIRONMENT["JOB_ID"]]) == 1
    assert "teaching_login_failure" not in json.loads(capsys.readouterr().out)


@pytest.mark.asyncio
async def test_failure_detail_survives_finalization_and_cleanup_without_retry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient([])
    session = FakeSession()
    calls = 0

    async def adapter(*_: object) -> int:
        nonlocal calls
        calls += 1
        raise cli.RunnerError("AUTH_FAILED", teaching_login_failure="request_send_failed")

    with pytest.raises(cli.RunnerError) as caught:
        await cli.run_job(
            JOB_ID, RUN_ENVIRONMENT, client_factory=lambda _: client,
            session_factory=lambda **_: session, adapter=adapter,
        )
    assert calls == 1
    assert len(client.finished) == 1
    assert client.finished[0][:4] == (RUN_ID, "failed", 0, "AUTH_FAILED")
    assert session.closed and session.stop_calls == 1
    report = tmp_path / "summary.md"
    cli._report_failure(caught.value, {**RUN_ENVIRONMENT, "GITHUB_STEP_SUMMARY": str(report)})
    assert json.loads(capsys.readouterr().out)["teaching_login_failure"] == "request_send_failed"
    assert "Không gửi được yêu cầu đăng nhập" in report.read_text(encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize("login", [False, True])
async def test_success_clears_old_failure_and_preserves_auth_mode(login: bool) -> None:
    browser = SuccessfulLoginBrowser(ContentPage(LOGIN_HTML if login else TEACHING_HTML))
    browser.teaching_login_failure = "request_send_failed"
    assert await readonly_site_adapter(CONFIG, claimed(PAYLOAD), browser) == 1
    assert browser.teaching_login_failure is None
    assert browser.teaching_auth_mode == ("password_login" if login else "saved_session")
    assert browser.login_calls == int(login)
