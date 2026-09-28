import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from mindx_runner.browser_driver import (
    BrowserNavigationError,
    BrowserStartupError,
    ReadonlyBrowserSession,
)


@dataclass
class FakePage:
    navigated: list[str] = field(default_factory=list)
    session_id: str = "session-1"

    async def goto(self, url: str) -> None:
        self.navigated.append(url)


@dataclass
class FakeSession:
    options: dict[str, Any]
    started: bool = False
    stopped: bool = False
    page: FakePage = field(default_factory=FakePage)
    cdp_client: Any = field(default_factory=lambda: FakeCdp())
    session_manager: Any = field(default_factory=lambda: FakeSessionManager())

    def __post_init__(self) -> None:
        self.session_manager.cdp = self.cdp_client
        self.cdp_client._event_registry._handlers["Target.attachedToTarget"] = (
            self.session_manager.on_attached
        )

    async def start(self) -> None:
        self.started = True

    async def new_page(self) -> FakePage:
        return self.page

    async def get_or_create_cdp_session(self, target_id: str, *, focus: bool = False) -> Any:
        return type("TargetSession", (), {"cdp_client": self.cdp_client, "session_id": target_id})()

    async def stop(self) -> None:
        self.stopped = True


def test_default_session_factory_disables_chromium_sandbox_on_github_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindx_runner.browser_driver as browser_driver

    created: dict[str, Any] = {}

    class StubBrowserSession:
        def __init__(self, **options: Any) -> None:
            created.update(options)

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        "browser_use.browser.BrowserSession",
        StubBrowserSession,
    )

    browser_driver._default_session_factory(headless=True)

    assert created["chromium_sandbox"] is False

    created.clear()
    monkeypatch.delenv("GITHUB_ACTIONS")
    browser_driver._default_session_factory(headless=True)

    assert "chromium_sandbox" not in created


@dataclass
class FakeFetchSend:
    enabled: list[tuple[dict[str, Any], str | None]] = field(default_factory=list)
    continued: list[tuple[dict[str, Any], str | None]] = field(default_factory=list)
    failed: list[tuple[dict[str, Any], str | None]] = field(default_factory=list)

    async def enable(self, *, params: dict[str, Any], session_id: str | None) -> None:
        self.enabled.append((params, session_id))

    async def continueRequest(self, *, params: dict[str, Any], session_id: str | None) -> None:
        self.continued.append((params, session_id))

    async def failRequest(self, *, params: dict[str, Any], session_id: str | None) -> None:
        self.failed.append((params, session_id))


@dataclass
class FakeFetchRegistration:
    callback: Any = None

    def requestPaused(self, callback: Any) -> None:
        self.callback = callback


@dataclass
class FakeTargetRegistration:
    handlers: dict[str, Any]

    def attachedToTarget(self, callback: Any) -> None:
        self.handlers["Target.attachedToTarget"] = callback


@dataclass
class FakeTargetSend:
    auto_attach: list[tuple[dict[str, Any], str | None]] = field(default_factory=list)
    closed: list[tuple[dict[str, Any], str | None]] = field(default_factory=list)
    events: list[str] | None = None

    async def setAutoAttach(
        self, *, params: dict[str, Any], session_id: str | None = None
    ) -> None:
        self.auto_attach.append((params, session_id))
        if self.events is not None:
            self.events.append(
                f"auto_attach:{params.get('waitForDebuggerOnStart')}"
            )

    async def closeTarget(
        self, *, params: dict[str, Any], session_id: str | None = None
    ) -> None:
        self.closed.append((params, session_id))


@dataclass
class FakeRuntimeSend:
    resumed: list[str | None] = field(default_factory=list)
    events: list[str] | None = None

    async def runIfWaitingForDebugger(self, *, session_id: str | None = None) -> None:
        self.resumed.append(session_id)
        if self.events is not None:
            self.events.append("resume")


@dataclass
class FakeEventRegistry:
    _handlers: dict[str, Any] = field(default_factory=dict)

    def register(self, method: str, callback: Any) -> None:
        self._handlers[method] = callback

    def get_registered_methods(self) -> list[str]:
        return list(self._handlers)


@dataclass
class FakeTargetSession:
    cdp_client: Any
    session_id: str


@dataclass
class FakeTarget:
    target_id: str


@dataclass
class FakeSessionManager:
    targets: list[FakeTarget] = field(default_factory=lambda: [FakeTarget("target-existing")])
    cdp: Any | None = None
    sessions: dict[str, FakeTargetSession] = field(default_factory=dict)
    handled_events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.cdp is not None and not self.sessions:
            self.sessions = {
                target.target_id: FakeTargetSession(self.cdp, target.target_id)
                for target in self.targets
            }

    def get_all_targets(self) -> dict[str, FakeTarget]:
        return {target.target_id: target for target in self.targets}

    def get_all_sessions(self) -> dict[str, FakeTargetSession]:
        return self.sessions

    def get_session(self, session_id: str) -> FakeTargetSession | None:
        return self.sessions.get(session_id)

    def on_attached(self, event: dict[str, Any], _session_id: str | None = None) -> None:
        attached_session_id = event.get("sessionId")
        if isinstance(attached_session_id, str) and self.cdp is not None:
            self.sessions[attached_session_id] = FakeTargetSession(
                self.cdp, attached_session_id
            )

    async def _handle_target_attached(self, event: dict[str, Any]) -> None:
        if self.cdp is not None:
            assert any(
                session_id == event.get("sessionId")
                for _, session_id in self.cdp.fetch_send.enabled
            )
        self.handled_events.append(dict(event))
        self.on_attached(event)
        if self.cdp is not None:
            await self.cdp.send.Target.setAutoAttach(
                params={
                    "autoAttach": True,
                    "waitForDebuggerOnStart": False,
                    "flatten": True,
                },
                session_id=event.get("sessionId"),
            )
            if event.get("waitingForDebugger") is True:
                await self.cdp.send.Runtime.runIfWaitingForDebugger(
                    session_id=event.get("sessionId")
                )



@dataclass
class FakeCdp:
    _event_registry: FakeEventRegistry = field(default_factory=FakeEventRegistry)
    fetch_send: FakeFetchSend = field(default_factory=FakeFetchSend)
    target_send: FakeTargetSend = field(default_factory=FakeTargetSend)
    runtime_send: FakeRuntimeSend = field(default_factory=FakeRuntimeSend)
    events: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.target_send.events = self.events
        self.runtime_send.events = self.events
        handlers = self._event_registry._handlers
        self.send = type(
            "Send",
            (),
            {
                "Fetch": self.fetch_send,
                "Target": self.target_send,
                "Runtime": self.runtime_send,
            },
        )()
        self.register = type(
            "Register",
            (),
            {
                "Fetch": FakeFetchRegistration(),
                "Target": FakeTargetRegistration(handlers),
            },
        )()


@pytest.mark.asyncio
async def test_readonly_browser_starts_with_safe_options_and_opens_allowlisted_url() -> None:
    created: list[FakeSession] = []

    def factory(**options: Any) -> FakeSession:
        session = FakeSession(options)
        created.append(session)
        return session

    browser = ReadonlyBrowserSession(session_factory=factory)

    page = await browser.open("https://lms.mindx.edu.vn/classes/synthetic")

    assert created[0].started is True
    assert created[0].options["headless"] is True
    assert created[0].options["allowed_domains"] == [
        "lms.mindx.edu.vn",
        "teachingmindx.top",
    ]
    assert created[0].options["enable_default_extensions"] is False
    assert created[0].options["captcha_solver"] is False
    assert created[0].options["keep_alive"] is False
    assert created[0].options["traces_dir"] is None
    assert created[0].options["record_video_dir"] is None
    assert page.navigated == ["https://lms.mindx.edu.vn/classes/synthetic"]
    assert created[0].cdp_client.target_send.auto_attach[0] == (
        {
            "autoAttach": True,
            "waitForDebuggerOnStart": True,
            "flatten": True,
        },
        None,
    )

    await browser.close()
    assert created[0].stopped is True


@pytest.mark.asyncio
async def test_readonly_browser_materializes_and_cleans_in_memory_storage_state() -> None:
    created: list[FakeSession] = []

    def factory(**options: Any) -> FakeSession:
        session = FakeSession(options)
        created.append(session)
        return session

    browser = ReadonlyBrowserSession(
        storage_state={
            "cookies": [
                {
                    "name": "sid",
                    "value": "synthetic-cookie",
                    "domain": ".teachingmindx.top",
                    "path": "/",
                }
            ],
            "origins": [],
        },
        session_factory=factory,
    )

    await browser.start()

    state_path = Path(str(created[0].options["storage_state"]))
    assert state_path.exists()
    assert Path(str(created[0].options["user_data_dir"])) == state_path.parent
    assert "synthetic-cookie" not in str(state_path)
    assert "synthetic-cookie" not in repr(created[0].options)
    assert json.loads(state_path.read_text(encoding="utf-8"))["cookies"][0]["value"] == (
        "synthetic-cookie"
    )

    await browser.close()
    assert not state_path.exists()


@pytest.mark.asyncio
async def test_readonly_browser_hides_startup_failure_and_cleans_storage_state() -> None:
    created: list[FakeSession] = []

    class FailingSession(FakeSession):
        async def start(self) -> None:
            raise RuntimeError("cookie=synthetic-cookie")

    def factory(**options: Any) -> FailingSession:
        session = FailingSession(options)
        created.append(session)
        return session

    browser = ReadonlyBrowserSession(
        storage_state={"cookies": [], "origins": []},
        session_factory=factory,
    )

    with pytest.raises(BrowserStartupError) as error:
        await browser.start()

    assert error.value.code == "BROWSER_STARTUP_FAILED"
    assert "synthetic-cookie" not in str(error.value)
    assert not Path(str(created[0].options["storage_state"])).exists()
    assert created[0].stopped is True


@pytest.mark.asyncio
async def test_readonly_browser_retries_locked_storage_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindx_runner.browser_driver as browser_driver

    original_rmtree = browser_driver.shutil.rmtree
    attempts = 0

    def flaky_rmtree(path: str, *args: Any, **kwargs: Any) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("temporary lock")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(browser_driver.shutil, "rmtree", flaky_rmtree)
    session = FakeSession({})
    browser = ReadonlyBrowserSession(
        storage_state={"cookies": [], "origins": []},
        session_factory=lambda **options: (session.options.update(options) or session),
    )

    await browser.start()
    state_path = Path(str(session.options["storage_state"]))
    await browser.close()

    assert attempts >= 2
    assert not state_path.exists()


@pytest.mark.asyncio
async def test_readonly_browser_hides_navigation_failure() -> None:
    class FailingPage(FakePage):
        async def goto(self, url: str) -> None:
            raise RuntimeError("cookie=synthetic-cookie")

    session = FakeSession({})
    session.page = FailingPage()
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    with pytest.raises(BrowserNavigationError) as error:
        await browser.open("https://teachingmindx.top/schedule")

    assert error.value.code == "BROWSER_NAVIGATION_FAILED"
    assert "synthetic-cookie" not in str(error.value)
    await browser.close()


@pytest.mark.asyncio
async def test_readonly_browser_accepts_explicit_login_paths_before_start() -> None:
    session = FakeSession({})
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    browser.configure_login_paths(("/auth/login",))
    await browser.open("https://teachingmindx.top/schedule")
    fetch_send = session.cdp_client.send.Fetch
    callback = session.cdp_client.register.Fetch.callback

    callback(
        {
            "requestId": "login-1",
            "request": {
                "url": "https://teachingmindx.top/auth/login",
                "method": "POST",
                "postData": "username=owner",
                "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            },
        },
        "session-1",
    )
    await asyncio.sleep(0)

    assert fetch_send.continued == [({"requestId": "login-1"}, "session-1")]
    await browser.close()


@pytest.mark.asyncio
async def test_readonly_browser_rejects_unsafe_url_before_creating_page() -> None:
    created: list[FakeSession] = []

    def factory(**options: Any) -> FakeSession:
        session = FakeSession(options)
        created.append(session)
        return session

    browser = ReadonlyBrowserSession(session_factory=factory)

    with pytest.raises(RuntimeError, match="Domain is not allowlisted"):
        await browser.open("https://evil.example/submit")

    assert created == []
    await browser.close()


@pytest.mark.asyncio
async def test_readonly_browser_close_is_idempotent() -> None:
    session = FakeSession({})
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    await browser.close()
    await browser.open("https://teachingmindx.top/login")
    await browser.close()
    await browser.close()

    assert session.stopped is True


@pytest.mark.asyncio
async def test_readonly_browser_stops_when_guard_setup_is_unavailable() -> None:
    session = FakeSession({})
    session.cdp_client.target_send = None
    session.cdp_client.send.Target = None
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    with pytest.raises(RuntimeError, match="BROWSER_NETWORK_GUARD_UNAVAILABLE"):
        await browser.start()

    assert session.stopped is True


@pytest.mark.asyncio
async def test_readonly_browser_intercepts_and_fails_mutation_request() -> None:
    session = FakeSession({})
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    await browser.open("https://lms.mindx.edu.vn/classes/synthetic")
    fetch_send = session.cdp_client.send.Fetch
    callback = session.cdp_client.register.Fetch.callback

    callback(
        {
            "requestId": "request-1",
            "request": {
                "url": "https://lms.mindx.edu.vn/api/reviews",
                "method": "POST",
                "postData": "comment=must-not-submit",
                "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            },
        },
        "session-1",
    )
    await asyncio.sleep(0)

    assert fetch_send.failed == [
        ({"requestId": "request-1", "errorReason": "BlockedByClient"}, "session-1")
    ]
    assert fetch_send.continued == []
    await browser.close()


@pytest.mark.asyncio
async def test_readonly_browser_continues_allowlisted_read_request() -> None:
    session = FakeSession({})
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    await browser.open("https://lms.mindx.edu.vn/classes/synthetic")
    fetch_send = session.cdp_client.send.Fetch
    callback = session.cdp_client.register.Fetch.callback

    callback(
        {
            "requestId": "request-2",
            "request": {
                "url": "https://lms.mindx.edu.vn/api/classes",
                "method": "GET",
                "headers": {},
            },
        },
        "session-1",
    )
    await asyncio.sleep(0)

    assert fetch_send.continued == [({"requestId": "request-2"}, "session-1")]
    assert fetch_send.failed == []
    await browser.close()


@pytest.mark.asyncio
async def test_readonly_browser_fails_closed_when_cdp_fetch_is_unavailable() -> None:
    session = FakeSession({})
    session.cdp_client = None
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    with pytest.raises(RuntimeError, match="BROWSER_NETWORK_GUARD_UNAVAILABLE"):
        await browser.open("https://lms.mindx.edu.vn/classes/synthetic")

    await browser.close()


@pytest.mark.asyncio
async def test_readonly_browser_guards_existing_and_future_targets() -> None:
    session = FakeSession({})
    browser = ReadonlyBrowserSession(session_factory=lambda **_: session)

    await browser.start()

    fetch_send = session.cdp_client.send.Fetch
    assert fetch_send.enabled == [
        ({"patterns": [{"urlPattern": "*", "requestStage": "Request"}]}, "target-existing")
    ]

    attached_handler = session.cdp_client._event_registry._handlers[
        "Target.attachedToTarget"
    ]
    attached_handler(
        {
            "sessionId": "target-future",
            "waitingForDebugger": True,
            "targetInfo": {"targetId": "target-future", "type": "page"},
        },
        None,
    )
    await asyncio.sleep(0)

    assert fetch_send.enabled[-1] == (
        {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]},
        "target-future",
    )
    assert session.session_manager.handled_events[-1]["waitingForDebugger"] is False
    assert session.cdp_client.target_send.auto_attach[-1] == (
        {
            "autoAttach": True,
            "waitForDebuggerOnStart": True,
            "flatten": True,
        },
        "target-future",
    )
    assert session.cdp_client.runtime_send.resumed == ["target-future"]
    assert session.cdp_client.events[-2:] == ["auto_attach:True", "resume"]
    await browser.close()


@pytest.mark.parametrize("target_type", ["page", "tab", "iframe", "worker"])
def test_readonly_browser_guards_web_target_types(target_type: str) -> None:
    assert ReadonlyBrowserSession._target_requires_guard(
        {"type": target_type, "url": "https://teachingmindx.top/"}
    ) is True
