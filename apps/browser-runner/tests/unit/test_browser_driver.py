from dataclasses import dataclass, field
from typing import Any

import pytest

from mindx_runner.browser_driver import ReadonlyBrowserSession


@dataclass
class FakePage:
    navigated: list[str] = field(default_factory=list)

    async def goto(self, url: str) -> None:
        self.navigated.append(url)


@dataclass
class FakeSession:
    options: dict[str, Any]
    started: bool = False
    stopped: bool = False
    page: FakePage = field(default_factory=FakePage)

    async def start(self) -> None:
        self.started = True

    async def new_page(self) -> FakePage:
        return self.page

    async def stop(self) -> None:
        self.stopped = True


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

    await browser.close()
    assert created[0].stopped is True


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
