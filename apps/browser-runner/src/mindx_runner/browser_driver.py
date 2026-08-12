from collections.abc import Callable
from typing import Any, Protocol

from .guardrails import ALLOWED_PRODUCTION_HOSTS
from .network_guard import classify_request


class BrowserPage(Protocol):
    async def goto(self, url: str) -> None:
        ...


class BrowserSessionLike(Protocol):
    async def start(self) -> None:
        ...

    async def new_page(self) -> BrowserPage:
        ...

    async def stop(self) -> None:
        ...


SessionFactory = Callable[..., BrowserSessionLike]


def _default_session_factory(**options: Any) -> BrowserSessionLike:
    from browser_use.browser import BrowserSession

    return BrowserSession(**options)


class ReadonlyBrowserSession:
    def __init__(
        self,
        *,
        storage_state: str | dict[str, object] | None = None,
        session_factory: SessionFactory = _default_session_factory,
        login_paths: tuple[str, ...] = (),
    ) -> None:
        self._storage_state = storage_state
        self._session_factory = session_factory
        self._login_paths = login_paths
        self._session: BrowserSessionLike | None = None

    async def _start(self) -> None:
        if self._session is not None:
            return
        self._session = self._session_factory(
            headless=True,
            allowed_domains=sorted(ALLOWED_PRODUCTION_HOSTS),
            storage_state=self._storage_state,
            enable_default_extensions=False,
            captcha_solver=False,
            keep_alive=False,
            traces_dir=None,
            record_video_dir=None,
            record_har_path=None,
        )
        await self._session.start()

    async def start(self) -> None:
        await self._start()

    async def open(self, url: str) -> BrowserPage:
        decision = classify_request("GET", url, login_paths=self._login_paths)
        if not decision.allowed:
            message = (
                "Domain is not allowlisted"
                if decision.code == "DOMAIN_BLOCKED"
                else decision.code
            )
            raise RuntimeError(message)
        await self._start()
        assert self._session is not None
        page = await self._session.new_page()
        await page.goto(url)
        return page

    async def close(self) -> None:
        if self._session is None:
            return
        session = self._session
        self._session = None
        await session.stop()
