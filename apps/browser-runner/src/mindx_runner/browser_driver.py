import asyncio
import inspect
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

    @property
    def cdp_client(self) -> Any:
        ...

    @property
    def session_manager(self) -> Any:
        ...

    async def get_or_create_cdp_session(self, target_id: str, *, focus: bool = False) -> Any:
        ...


SessionFactory = Callable[..., BrowserSessionLike]


class BrowserGuardError(RuntimeError):
    code = "BROWSER_NETWORK_GUARD_UNAVAILABLE"

    def __init__(self) -> None:
        super().__init__(self.code)


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
        self._guarded_session_ids: set[str] = set()
        self._guard_cdp: Any | None = None
        self._attach_tasks: set[asyncio.Task[None]] = set()
        self._guard_failed = False

    async def _start(self) -> None:
        if self._session is not None:
            return
        self._guard_failed = False
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
        try:
            await self._session.start()
            await self._install_target_guard()
        except BaseException:
            session = self._session
            self._session = None
            self._guarded_session_ids.clear()
            self._guard_cdp = None
            await self._cancel_attach_tasks()
            try:
                await session.stop()
            finally:
                raise

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
        await self._install_network_guard(page)
        if self._guard_failed:
            raise BrowserGuardError()
        await page.goto(url)
        return page

    async def _install_target_guard(self) -> None:
        assert self._session is not None
        cdp = getattr(self._session, "cdp_client", None)
        manager = getattr(self._session, "session_manager", None)
        if cdp is None or manager is None:
            raise BrowserGuardError()
        registration = getattr(getattr(cdp, "register", None), "Target", None)
        fetch_registration = getattr(getattr(cdp, "register", None), "Fetch", None)
        registry = getattr(cdp, "_event_registry", None)
        target_send = getattr(getattr(cdp, "send", None), "Target", None)
        if (
            registration is None
            or fetch_registration is None
            or registry is None
            or target_send is None
        ):
            raise BrowserGuardError()
        registered_methods: list[str] = getattr(registry, "get_registered_methods", lambda: [])()
        if "Fetch.requestPaused" in registered_methods:
            raise BrowserGuardError()

        existing_target_handler = getattr(registry, "_handlers", {}).get("Target.attachedToTarget")
        if existing_target_handler is None:
            raise BrowserGuardError()

        def on_attached(event: Any, session_id: str | None = None) -> None:
            task = asyncio.create_task(
                self._handle_attached_target(
                    event, session_id, cdp, manager, existing_target_handler
                )
            )
            self._attach_tasks.add(task)
            task.add_done_callback(self._on_attach_task_done)

        registry.register("Target.attachedToTarget", on_attached)
        fetch_registration.requestPaused(self._handle_request_paused)
        self._guard_cdp = cdp
        try:
            await target_send.setAutoAttach(
                params={
                    "autoAttach": True,
                    "waitForDebuggerOnStart": True,
                    "flatten": True,
                }
            )
        except Exception as exc:
            raise BrowserGuardError() from exc
        sessions: dict[str, Any] = getattr(manager, "get_all_sessions", lambda: {})()
        targets: dict[str, Any] = getattr(manager, "get_all_targets", lambda: {})()
        if sessions:
            for cdp_session in sessions.values():
                target_id = getattr(cdp_session, "target_id", None)
                target = targets.get(target_id) if isinstance(target_id, str) else None
                if self._target_requires_guard(target):
                    await self._guard_cdp_session(cdp_session, manager=manager)
        else:
            for target_id in manager.get_all_targets():
                cdp_session = await self._session.get_or_create_cdp_session(target_id, focus=False)
                target = targets.get(target_id)
                if self._target_requires_guard(target):
                    await self._guard_cdp_session(cdp_session, manager=manager)

    async def _handle_attached_target(
        self,
        event: Any,
        session_id: str | None,
        cdp: Any,
        manager: Any,
        existing_target_handler: Any,
    ) -> None:
        target_info = event.get("targetInfo")
        attached_session_id = event.get("sessionId")
        if not isinstance(attached_session_id, str):
            raise BrowserGuardError()
        if not self._target_requires_guard(target_info):
            result = existing_target_handler(event, session_id)
            if inspect.isawaitable(result):
                await result
            return

        try:
            # Browser Use's attach callback is scheduled asynchronously. Guard
            # the raw session first while Chrome is still waiting for a debugger.
            await self._guard_cdp_session(
                type(
                    "AttachedTargetSession",
                    (),
                    {"cdp_client": cdp, "session_id": attached_session_id},
                )(),
            )
            manager_event = dict(event)
            manager_event["waitingForDebugger"] = False
            result = existing_target_handler(manager_event, session_id)
            if inspect.isawaitable(result):
                await result
            await self._wait_for_and_guard_session(
                manager,
                attached_session_id,
                target_info,
            )
            await self._set_attached_target_auto_attach(attached_session_id)
            await self._resume_attached_target(event)
        except Exception:
            self._guard_failed = True
            await self._close_attached_target(event)

    def _on_attach_task_done(self, task: asyncio.Task[None]) -> None:
        self._attach_tasks.discard(task)
        if not task.cancelled():
            task.exception()

    @staticmethod
    def _target_requires_guard(target: Any) -> bool:
        """Guard web targets, not Browser Use's own Chrome extension targets."""
        if target is None:
            return True
        target_type = getattr(target, "target_type", None)
        target_url = getattr(target, "url", None)
        if isinstance(target, dict):
            target_type = target.get("type", target.get("target_type"))
            target_url = target.get("url")
        if target_type is not None and str(target_type) not in {
            "page",
            "iframe",
            "worker",
            "service_worker",
            "shared_worker",
            "webview",
        }:
            return False
        if isinstance(target_url, str) and target_url.startswith(
            ("chrome://", "chrome-extension://", "chrome-untrusted://", "devtools://")
        ):
            return False
        return True

    async def _wait_for_and_guard_session(
        self, manager: Any, session_id: str, target_info: Any = None
    ) -> None:
        if not self._target_requires_guard(target_info):
            return
        for _ in range(50):
            cdp_session = manager.get_session(session_id)
            if cdp_session is not None:
                await self._guard_cdp_session(cdp_session, manager=manager)
                return
            target_id = target_info.get("targetId") if isinstance(target_info, dict) else None
            if target_id and target_id not in manager.get_all_targets():
                return
            await asyncio.sleep(0.02)
        raise BrowserGuardError()

    async def _resume_attached_target(self, event: Any) -> None:
        if event.get("waitingForDebugger") is not True:
            return
        runtime_send = getattr(getattr(self._guard_cdp, "send", None), "Runtime", None)
        if runtime_send is None:
            raise BrowserGuardError()
        try:
            await runtime_send.runIfWaitingForDebugger(session_id=event["sessionId"])
        except Exception as exc:
            raise BrowserGuardError() from exc

    async def _set_attached_target_auto_attach(self, session_id: str) -> None:
        target_send = getattr(getattr(self._guard_cdp, "send", None), "Target", None)
        if target_send is None:
            raise BrowserGuardError()
        try:
            await target_send.setAutoAttach(
                params={
                    "autoAttach": True,
                    "waitForDebuggerOnStart": True,
                    "flatten": True,
                },
                session_id=session_id,
            )
        except Exception as exc:
            raise BrowserGuardError() from exc

    async def _close_attached_target(self, event: Any) -> None:
        target_id = (event.get("targetInfo") or {}).get("targetId")
        target_send = getattr(getattr(self._guard_cdp, "send", None), "Target", None)
        if not isinstance(target_id, str) or target_send is None:
            return
        try:
            await target_send.closeTarget(params={"targetId": target_id})
        except Exception:
            pass

    async def _guard_cdp_session(self, cdp_session: Any, *, manager: Any = None) -> None:
        target_session_id = getattr(cdp_session, "session_id", None)
        if target_session_id in self._guarded_session_ids:
            return
        if not isinstance(target_session_id, str) or not target_session_id:
            raise BrowserGuardError()
        target_cdp = getattr(cdp_session, "cdp_client", None)
        if target_cdp is None or not isinstance(target_session_id, str):
            raise BrowserGuardError()
        fetch_send = getattr(getattr(target_cdp, "send", None), "Fetch", None)
        if fetch_send is None:
            raise BrowserGuardError()
        for _ in range(5):
            try:
                await fetch_send.enable(
                    params={"patterns": [{"urlPattern": "*", "requestStage": "Request"}]},
                    session_id=target_session_id,
                )
                break
            except RuntimeError as exc:
                if "Session with given id not found" not in str(exc):
                    raise
                if manager is not None and manager.get_session(target_session_id) is None:
                    raise BrowserGuardError() from exc
                await asyncio.sleep(0.02)
        else:
            raise BrowserGuardError()
        self._guarded_session_ids.add(target_session_id)

    async def _install_network_guard(self, page: BrowserPage) -> None:
        """Pause every page request and apply the read-only network policy."""
        assert self._session is not None
        cdp = getattr(self._session, "cdp_client", None)
        session_id = getattr(page, "session_id", None)
        if cdp is None or session_id is None:
            raise BrowserGuardError()
        if inspect.isawaitable(session_id):
            session_id = await session_id
        if session_id in self._guarded_session_ids:
            return
        if not isinstance(session_id, str) or not session_id:
            raise BrowserGuardError()

        page_session = type(
            "PageSession", (), {"cdp_client": cdp, "session_id": session_id}
        )()
        await self._guard_cdp_session(page_session)

    async def _handle_request_paused(self, event: Any, session_id: str | None = None) -> None:
        cdp = self._guard_cdp
        if cdp is None:
            return
        request_id = event.get("requestId")
        request = event.get("request") or {}
        if not request_id:
            return

        fetch_send = cdp.send.Fetch
        try:
            method = str(request.get("method", ""))
            body = request.get("postData")
            if (
                method.upper() == "POST"
                and request.get("hasPostData") is True
                and not isinstance(body, str)
            ):
                raise RuntimeError("UNKNOWN_REQUEST_BODY")
            body_bytes = body.encode("utf-8", errors="ignore") if isinstance(body, str) else None
            headers = request.get("headers") or {}
            content_type = next(
                (
                    value
                    for key, value in headers.items()
                    if str(key).lower() == "content-type" and isinstance(value, str)
                ),
                None,
            )
            decision = classify_request(
                method,
                str(request.get("url", "")),
                body=body_bytes,
                content_type=content_type,
                login_paths=self._login_paths,
            )
            if decision.allowed:
                await fetch_send.continueRequest(
                    params={"requestId": request_id},
                    session_id=session_id,
                )
                return
        except Exception:
            pass
        try:
            await fetch_send.failRequest(
                params={"requestId": request_id, "errorReason": "BlockedByClient"},
                session_id=session_id,
            )
        except Exception:
            pass

    async def close(self) -> None:
        if self._session is None:
            return
        session = self._session
        self._session = None
        self._guarded_session_ids.clear()
        self._guard_cdp = None
        await self._cancel_attach_tasks()
        await session.stop()

    async def _cancel_attach_tasks(self) -> None:
        tasks = tuple(self._attach_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._attach_tasks.clear()
