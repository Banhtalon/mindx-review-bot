"""Recognize the official password form without retaining field values."""

from html.parser import HTMLParser
from urllib.parse import urljoin

LOGIN_URL = "https://teachingmindx.top/login.php"


class _AuthPage(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[tuple[str, str, list[tuple[str, str]]]] = []
        self.current: list[tuple[str, str]] | None = None
        self.challenge = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag == "form":
            self.current = []
            self.forms.append(
                (data.get("method", "get") or "get", data.get("action", "") or "", self.current)
            )
        if tag == "input":
            name = (data.get("name") or "").lower()
            if data.get("autocomplete") == "one-time-code" or name in {
                "otp",
                "otp_code",
                "verification_code",
            }:
                self.challenge = True
            if self.current is not None:
                self.current.append((name, (data.get("type") or "text").lower()))
        if any(marker in (data.get("src") or "").lower() for marker in ("captcha", "turnstile")):
            self.challenge = True
        if any(marker in (data.get("class") or "").lower() for marker in ("captcha", "turnstile")):
            self.challenge = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.current = None


def teaching_auth_state(html: str) -> str:
    parser = _AuthPage()
    parser.feed(html)
    if parser.challenge:
        return "challenge"
    forms = [
        (method, action, fields)
        for method, action, fields in parser.forms
        if any(kind == "password" for _, kind in fields)
    ]
    if not forms:
        return "none"
    if len(forms) != 1:
        return "invalid"
    method, action, fields = forms[0]
    if (
        method.lower() != "post"
        or urljoin(LOGIN_URL, action) != LOGIN_URL
        or fields.count(("username", "text")) != 1
        or fields.count(("password", "password")) != 1
        or any(name not in {"username", "password", "redirect", "remember"} for name, _ in fields)
    ):
        return "invalid"
    return "login"


LOGIN_SCRIPT = """(username, password) => {
    if (location.origin !== 'https://teachingmindx.top'
        || location.pathname !== '/login.php') return 'INVALID';
    const challenge = ['[autocomplete="one-time-code"]', 'input[name="otp"]',
        'input[name="otp_code"]', 'input[name="verification_code"]', '[class*="captcha"]',
        '[class*="turnstile"]', 'iframe[src*="captcha"]', 'script[src*="captcha"]',
        'script[src*="turnstile"]'].join(',');
    if (document.querySelector(challenge)) return 'CHALLENGE';
    const forms = Array.from(document.forms).filter(f => f.querySelector('input[type="password"]'));
    if (forms.length !== 1) return 'INVALID';
    const form = forms[0], action = new URL(form.action, location.href);
    if (form.method.toLowerCase() !== 'post'
        || action.href !== 'https://teachingmindx.top/login.php') return 'INVALID';
    const user = form.querySelectorAll('input[name="username"]');
    const pass = form.querySelectorAll('input[name="password"][type="password"]');
    if (user.length !== 1 || pass.length !== 1) return 'INVALID';
    for (const field of form.elements) {
        if (field.name
            && !['username', 'password', 'redirect', 'remember'].includes(field.name)) {
            return 'INVALID';
        }
    }
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    set.call(user[0], username); set.call(pass[0], password);
    for (const field of form.elements) {
        if (field.name === 'remember') field.disabled = true;
        if (field.name === 'redirect') set.call(field, '/');
    }
    window.__mindxLoginPending = true;
    HTMLFormElement.prototype.requestSubmit.call(form);
    return 'LOGIN_SENT';
}"""
