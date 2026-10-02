import json
import logging
import subprocess
from dataclasses import replace
from urllib.parse import urlencode

import pytest
from test_browser_driver import FakeCdp, FakePage, FakeSession
from test_live_adapter import CONFIG, TEACHING_HTML, FakeBrowser, claimed
from test_live_adapter import FakePage as ContentPage

from mindx_runner.browser_driver import ReadonlyBrowserSession
from mindx_runner.cli import RunnerError
from mindx_runner.live_adapter import readonly_site_adapter
from mindx_runner.teaching_auth import LOGIN_SCRIPT, LOGIN_URL, teaching_auth_state

LOGIN_HTML = (
    '<form method="POST"><input name="redirect" type="hidden">'
    '<input name="username" type="text"><input name="password" type="password">'
    '<input name="remember" type="checkbox"><button type="submit">Login</button></form>'
    '<form method="POST"><input name="fp_username"><button name="forgot_password"></button></form>'
)
USER = "synthetic@example.invalid"
PASSWORD = "synthetic-login-value"
PAYLOAD = {"teaching_url": "https://teachingmindx.top/", "allowed_class_codes": ["SYN-ROBOTICS-01"]}


@pytest.mark.parametrize(
    ("html", "state"),
    [
        (LOGIN_HTML, "login"),
        (TEACHING_HTML, "none"),
        (
            LOGIN_HTML.replace(
                '<form method="POST">',
                '<form method="POST" action="https://lms.mindx.edu.vn/login">',
                1,
            ),
            "invalid",
        ),
        (
            LOGIN_HTML.replace('<form method="POST">', '<form method="POST" action="/save">', 1),
            "invalid",
        ),
        (LOGIN_HTML.replace('name="username"', 'name="other"'), "invalid"),
        (LOGIN_HTML + '<input name="otp" autocomplete="one-time-code">', "challenge"),
        (LOGIN_HTML + '<iframe src="https://example.invalid/captcha"></iframe>', "challenge"),
        (LOGIN_HTML + LOGIN_HTML, "invalid"),
    ],
)
def test_login_form_recognition_rejects_ambiguous_or_unsafe_pages(html: str, state: str) -> None:
    assert teaching_auth_state(html) == state


@pytest.mark.asyncio
async def test_missing_credentials_and_non_login_error_never_attempt_login() -> None:
    browser = FakeBrowser(ContentPage(LOGIN_HTML))
    with pytest.raises(RunnerError, match="^TEACHING_LOGIN_REQUIRED$"):
        await readonly_site_adapter(
            replace(CONFIG, teaching_password=""), claimed(PAYLOAD), browser
        )
    browser = FakeBrowser(ContentPage("<html>Loading schedule failed</html>"))
    with pytest.raises(RunnerError, match="^TEACHING_DATA_INVALID$"):
        await readonly_site_adapter(CONFIG, claimed(PAYLOAD), browser)
    assert len(browser.opened) == 1


@pytest.mark.asyncio
async def test_failed_login_stops_and_sanitizes_exception() -> None:
    class LoginBrowser(FakeBrowser):
        calls = 0

        async def login_teaching(self, page: ContentPage, username: str, password: str) -> None:
            self.calls += 1
            raise ValueError(PASSWORD)

    browser = LoginBrowser(ContentPage(LOGIN_HTML))
    with pytest.raises(RunnerError, match="^AUTH_FAILED$") as error:
        await readonly_site_adapter(CONFIG, claimed(PAYLOAD), browser)
    assert PASSWORD not in str(error.value)
    assert error.value.__suppress_context__
    assert browser.calls == 1


def event(url: str = LOGIN_URL, body: str | None = None) -> dict[str, object]:
    return {
        "requestId": "synthetic-login",
        "request": {
            "method": "POST",
            "url": url,
            "hasPostData": True,
            "postData": body
            if body is not None
            else urlencode({"username": USER, "password": PASSWORD, "redirect": "/"}),
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        },
    }


@pytest.mark.asyncio
async def test_network_boundary_permits_one_exact_login_then_blocks_repetition() -> None:
    browser = ReadonlyBrowserSession()
    cdp = FakeCdp()
    browser._guard_cdp = cdp
    browser._teaching_login_used = True
    browser._teaching_login_pending = (USER, PASSWORD)
    await browser._handle_request_paused(event(), "session-1")
    await browser._handle_request_paused(event(), "session-1")
    assert len(cdp.fetch_send.continued) == 1
    assert len(cdp.fetch_send.failed) == 1
    assert browser._teaching_login_pending is None


@pytest.mark.parametrize(
    ("url", "body"),
    [
        ("https://lms.mindx.edu.vn/login.php", None),
        (LOGIN_URL + "?action=save", None),
        ("https://teachingmindx.top/save", None),
        (LOGIN_URL, urlencode({"username": USER, "password": "wrong-value"})),
        (
            LOGIN_URL,
            urlencode(
                {"username": USER, "password": PASSWORD, "redirect": "https://example.invalid"}
            ),
        ),
        (LOGIN_URL, urlencode({"username": USER, "password": PASSWORD, "save": "1"})),
        (LOGIN_URL, urlencode({"username": USER, "password": PASSWORD}) + "&username=duplicate"),
    ],
)
@pytest.mark.asyncio
async def test_login_permission_cannot_allow_other_destinations_or_bodies(
    url: str, body: str | None
) -> None:
    browser = ReadonlyBrowserSession(login_paths=("/save", "/login.php"))
    cdp = FakeCdp()
    browser._guard_cdp = cdp
    browser._teaching_login_used = True
    browser._teaching_login_pending = (USER, PASSWORD)
    await browser._handle_request_paused(event(url, body), "session-1")
    assert not cdp.fetch_send.continued
    assert len(cdp.fetch_send.failed) == 1


@pytest.mark.asyncio
async def test_browser_login_hides_library_logs_and_cannot_submit_twice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    browser = ReadonlyBrowserSession()
    session = FakeSession({})
    browser._session = session
    browser._guard_cdp = session.cdp_client

    class LoginPage(FakePage):
        async def evaluate(self, script: str, *args: str) -> str:
            if args:
                logging.getLogger("browser_use.synthetic").error(PASSWORD)
                await browser._handle_request_paused(event(), self.session_id)
                return "LOGIN_SENT"
            return "COMPLETE"

    original = logging.root.manager.disable
    try:
        await browser.login_teaching(LoginPage(), USER, PASSWORD)
        with pytest.raises(RuntimeError, match="^AUTH_FAILED$"):
            await browser.login_teaching(LoginPage(), USER, PASSWORD)
        assert PASSWORD not in caplog.text
        assert len(session.cdp_client.fetch_send.continued) == 1
    finally:
        await browser.close()
    assert logging.root.manager.disable == original


def test_actual_login_script_validates_before_filling_and_leaves_remember_off() -> None:
    # Execute the production JavaScript against a synthetic DOM, never a real account.
    harness = """
const assert = require('node:assert/strict');
class Input { constructor(name) { this.name = name; this._value = ''; } }
Object.defineProperty(Input.prototype, 'value', {
    set(value) { this._value = value; }, get() { return this._value; }
});
const username = new Input('username'), password = new Input('password');
const redirect = new Input('redirect'), remember = new Input('remember');
let submits = 0, challenged = false;
class Form { requestSubmit() { submits++; } }
const form = new Form();
form.action = 'https://teachingmindx.top/login.php'; form.method = 'post';
form.elements = [username, password, redirect, remember];
form.querySelector = () => password;
form.querySelectorAll = selector => selector.includes('username') ? [username] : [password];
global.HTMLInputElement = Input; global.HTMLFormElement = Form; global.window = {};
global.location = {origin: 'https://teachingmindx.top', pathname: '/login.php',
    href: 'https://teachingmindx.top/login.php'};
global.document = {forms: [form], querySelector: () => challenged};
const login = eval('(' + SCRIPT + ')');
location.origin = 'https://lms.mindx.edu.vn';
assert.equal(login('synthetic-user', 'synthetic-pass'), 'INVALID');
assert.equal(password.value, ''); assert.equal(submits, 0);
location.origin = 'https://teachingmindx.top'; challenged = true;
assert.equal(login('synthetic-user', 'synthetic-pass'), 'CHALLENGE');
assert.equal(password.value, ''); challenged = false;
form.action = 'https://example.invalid/steal';
assert.equal(login('synthetic-user', 'synthetic-pass'), 'INVALID');
assert.equal(password.value, '');
form.action = location.href;
assert.equal(login('synthetic-user', 'synthetic-pass'), 'LOGIN_SENT');
assert.equal(password.value, 'synthetic-pass'); assert.equal(redirect.value, '/');
assert.equal(remember.disabled, true); assert.equal(submits, 1);
console.log('synthetic login script PASS');
"""
    result = subprocess.run(
        ["node"],
        input="const SCRIPT = " + json.dumps(LOGIN_SCRIPT) + ";\n" + harness,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
