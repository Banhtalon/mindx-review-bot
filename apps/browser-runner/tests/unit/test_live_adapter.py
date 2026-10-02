import asyncio
import traceback
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from mindx_runner.cli import RunnerError
from mindx_runner.live_adapter import _page_html, readonly_site_adapter
from mindx_runner.live_runner import LiveRunConfig
from mindx_runner.supabase_client import ClaimedRun

JOB_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
WORKSPACE_ID = "00000000-0000-4000-8000-000000000003"


_SUPABASE_TEST_VALUE = "server-secret"


CONFIG = LiveRunConfig(
    job_id=JOB_ID,
    runner_id="runner-test-01",
    job_type="sync_teaching",
    supabase_url="https://example.supabase.co",
    **{"supabase_secret_key": _SUPABASE_TEST_VALUE},
    browser_state_key=b"k" * 32,
    teaching_username="teacher@example.invalid",
    teaching_password="password",
    lms_username="",
    lms_password="",
)


@dataclass
class FakePage:
    html: str

    async def get_content(self) -> str:
        return self.html


@dataclass
class FakeBrowser:
    page: FakePage
    opened: list[str] = field(default_factory=list)
    configured_login_paths: tuple[str, ...] | None = None

    def configure_login_paths(self, paths: tuple[str, ...]) -> None:
        self.configured_login_paths = paths

    async def open(self, url: str) -> FakePage:
        self.opened.append(url)
        return self.page


def claimed(payload: dict[str, object], *, job_type: str = "sync_teaching") -> ClaimedRun:
    return ClaimedRun(
        claimed=True,
        run_id=RUN_ID,
        job_id=JOB_ID,
        workspace_id=WORKSPACE_ID,
        job_type=job_type,  # type: ignore[arg-type]
        payload=payload,
        attempt=1,
    )


TEACHING_HTML = """
<main data-teaching-schedule="true">
  <section data-teaching-session="true" data-class-code="SYN-ROBOTICS-01"
    data-source-session-id="teach-001" data-session-number="3"
    data-scheduled-date="2026-09-27" data-start-time="09:00:00"
    data-end-time="10:00:00">Robotics</section>
</main>
"""


LMS_HTML = """
<main data-lms-context="true" data-class-code="SYN-CLASS-01"
  data-session-number="3" data-scheduled-date="2026-09-27"
  data-start-time="09:00:00" data-end-time="10:00:00"
  data-source-session-id="lms-001" data-lesson="Robotics">
  <div data-lms-student="true" data-student-id="student-001"
    data-discriminator="profile-001" data-attendance="present">Student Alpha</div>
</main>
"""

LIVE_TEACHING_HTML = (
    Path(__file__).parents[1] / "fixtures" / "teaching" / "live-week.html"
).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_teaching_adapter_reads_html_and_configures_explicit_login_paths() -> None:
    browser = FakeBrowser(FakePage(TEACHING_HTML))

    count = await readonly_site_adapter(
        CONFIG,
        claimed(
            {
                "teaching_url": "https://teachingmindx.top/schedule",
                "allowed_class_codes": ["SYN-ROBOTICS-01"],
                "expected_class_code": "SYN-ROBOTICS-01",
                "expected_session_number": 3,
                "login_paths": ["/login"],
            }
        ),
        browser,
    )

    assert count == 1
    assert browser.opened == ["https://teachingmindx.top/schedule"]
    assert browser.configured_login_paths == ("/login",)


@pytest.mark.asyncio
async def test_teaching_adapter_reads_html_from_browser_use_page_evaluate() -> None:
    class EvaluateOnlyPage:
        async def evaluate(self, expression: str) -> str:
            return "READY:" + TEACHING_HTML

    class EvaluateOnlyBrowser(FakeBrowser):
        async def open(self, url: str) -> EvaluateOnlyPage:
            self.opened.append(url)
            return EvaluateOnlyPage()

    browser = EvaluateOnlyBrowser(FakePage(TEACHING_HTML))

    count = await readonly_site_adapter(
        CONFIG,
        claimed(
            {
                "teaching_url": "https://teachingmindx.top/schedule",
                "allowed_class_codes": ["SYN-ROBOTICS-01"],
                "expected_class_code": "SYN-ROBOTICS-01",
                "expected_session_number": 3,
            }
        ),
        browser,
    )

    assert count == 1
    assert browser.opened == ["https://teachingmindx.top/schedule"]


@pytest.mark.asyncio
async def test_adapter_maps_opaque_browser_open_failure_to_safe_code() -> None:
    class FailingBrowser(FakeBrowser):
        async def open(self, url: str) -> FakePage:
            raise RuntimeError("cookie=synthetic-cookie")

    browser = FailingBrowser(FakePage(TEACHING_HTML))

    with pytest.raises(RunnerError) as error:
        await readonly_site_adapter(
            CONFIG,
            claimed(
                {
                    "teaching_url": "https://teachingmindx.top/schedule",
                    "allowed_class_codes": ["SYN-ROBOTICS-01"],
                }
            ),
            browser,
        )

    assert error.value.code == "BROWSER_NAVIGATION_FAILED"
    assert "synthetic-cookie" not in str(error.value)


@pytest.mark.asyncio
async def test_teaching_adapter_reads_owner_selected_live_schedule() -> None:
    browser = FakeBrowser(FakePage(LIVE_TEACHING_HTML))

    count = await readonly_site_adapter(
        CONFIG,
        claimed(
            {
                "teaching_url": "https://teachingmindx.top/",
                "allowed_class_codes": ["VT-CSI02"],
                "expected_class_code": "VT-CSI02",
                "expected_session_number": 6,
            }
        ),
        browser,
    )

    assert count == 1
    assert browser.opened == ["https://teachingmindx.top/"]


@pytest.mark.asyncio
async def test_lms_adapter_reads_only_the_configured_page_and_counts_students() -> None:
    browser = FakeBrowser(FakePage(LMS_HTML))
    config = LiveRunConfig(
        job_id=JOB_ID,
        runner_id="runner-test-01",
        job_type="read_lms_pending",
        supabase_url=CONFIG.supabase_url,
        **{"supabase_secret_key": _SUPABASE_TEST_VALUE},
        browser_state_key=b"k" * 32,
        teaching_username="",
        teaching_password="",
        lms_username="teacher@example.invalid",
        lms_password="password",
    )

    count = await readonly_site_adapter(
        config,
        claimed(
            {
                "lms_url": "https://lms.mindx.edu.vn/class/session",
                "allowed_class_codes": ["SYN-CLASS-01"],
                "expected_class_code": "SYN-CLASS-01",
                "expected_session_number": 3,
            },
            job_type="read_lms_pending",
        ),
        browser,
    )

    assert count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"teaching_url": "https://evil.example/schedule"},
        {"teaching_url": "https://lms.mindx.edu.vn/submit"},
        {"teaching_url": "http://teachingmindx.top/schedule"},
    ],
)
async def test_adapter_rejects_non_allowlisted_or_mutating_url(
    payload: dict[str, object],
) -> None:
    browser = FakeBrowser(FakePage(TEACHING_HTML))

    with pytest.raises(RunnerError) as error:
        await readonly_site_adapter(CONFIG, claimed(payload), browser)

    assert error.value.code in {"DOMAIN_BLOCKED", "LMS_MUTATION_BLOCKED"}
    assert browser.opened == []


@pytest.mark.asyncio
async def test_adapter_honors_explicit_payload_url_allowlist() -> None:
    browser = FakeBrowser(FakePage(TEACHING_HTML))

    with pytest.raises(RunnerError) as error:
        await readonly_site_adapter(
            CONFIG,
            claimed(
                {
                    "teaching_url": "https://teachingmindx.top/other",
                    "allowed_urls": ["https://teachingmindx.top/schedule"],
                    "allowed_class_codes": ["SYN-ROBOTICS-01"],
                }
            ),
            browser,
        )

    assert error.value.code == "DOMAIN_BLOCKED"
    assert browser.opened == []


@pytest.mark.asyncio
async def test_adapter_rejects_job_type_mismatch_before_navigation() -> None:
    browser = FakeBrowser(FakePage(TEACHING_HTML))

    with pytest.raises(RunnerError) as error:
        await readonly_site_adapter(
            CONFIG,
            claimed(
                {"teaching_url": "https://teachingmindx.top/schedule"},
                job_type="read_lms_pending",
            ),
            browser,
        )

    assert error.value.code == "JOB_TYPE_MISMATCH"
    assert browser.opened == []


@pytest.mark.asyncio
async def test_adapter_fails_closed_when_page_content_is_unavailable() -> None:
    class NoContentBrowser(FakeBrowser):
        async def open(self, url: str) -> object:
            return object()

    browser = NoContentBrowser(FakePage(TEACHING_HTML))

    with pytest.raises(RunnerError) as error:
        await readonly_site_adapter(
            CONFIG,
            claimed(
                {
                    "teaching_url": "https://teachingmindx.top/schedule",
                    "allowed_class_codes": ["SYN-ROBOTICS-01"],
                }
            ),
            browser,
        )

    assert error.value.code == "PAGE_CONTENT_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("job_type", ["sync_teaching", "read_lms_pending"])
@pytest.mark.parametrize("case", ["ready", "wrong_class", "wrong_session", "login"])
async def test_evaluate_waits_for_loading_and_blank_then_reads_one_snapshot(
    job_type: str, case: str,
) -> None:
    html = TEACHING_HTML if job_type == "sync_teaching" else LMS_HTML
    code = "SYN-ROBOTICS-01" if job_type == "sync_teaching" else "SYN-CLASS-01"
    if case == "login":
        html = '<main data-page-state="login"></main>'

    class LoadingPage:
        calls = 0

        async def evaluate(self, expression: str) -> str:
            self.calls += 1
            # A premature outerHTML read gets an incomplete but nonempty document.
            if "readyState" not in expression:
                return "<html><body></body></html>"
            assert "complete" in expression
            assert "document.documentElement" in expression
            assert "document.body" in expression
            assert "about:blank" in expression
            assert "location.href" in expression
            assert "outerHTML" in expression
            return "" if self.calls < 3 else "READY:" + html

    page = LoadingPage()

    class LoadingBrowser:
        async def open(self, url: str) -> LoadingPage:
            return page

    read = readonly_site_adapter(
        replace(CONFIG, job_type=job_type),  # type: ignore[arg-type]
        claimed(
            {
                "url": (
                    "https://teachingmindx.top/schedule" if job_type == "sync_teaching"
                    else "https://lms.mindx.edu.vn/class/session"
                ),
                "allowed_class_codes": [code],
                "expected_class_code": "OTHER-CLASS" if case == "wrong_class" else code,
                "expected_session_number": 99 if case == "wrong_session" else 3,
            },
            job_type=job_type,
        ),
        LoadingBrowser(),
    )
    if case == "ready":
        assert await read == 1
    else:
        with pytest.raises(RunnerError) as error:
            await read
        assert error.value.code == {
            "wrong_class": "CLASS_IDENTITY_MISMATCH",
            "wrong_session": "SESSION_IDENTITY_MISMATCH",
            "login": (
                "TEACHING_LOGIN_REQUIRED" if job_type == "sync_teaching" else "LMS_LOGIN_REQUIRED"
            ),
        }[case]
    assert page.calls == 3  # No separate read after the ready snapshot.


@pytest.mark.asyncio
@pytest.mark.parametrize("hang", [False, True])
async def test_evaluate_total_deadline_includes_polling_and_hanging_call(hang: bool) -> None:
    class NeverReadyPage:
        calls = 0
        cancelled = False

        async def evaluate(self, expression: str) -> str:
            self.calls += 1
            # First poll consumes part of the same deadline as the next call.
            if hang and self.calls > 1:
                try:
                    await asyncio.Event().wait()
                finally:
                    self.cancelled = True
            await asyncio.sleep(0.2)
            return ""

    page = NeverReadyPage()
    started = asyncio.get_running_loop().time()
    async with asyncio.timeout(12):
        with pytest.raises(RunnerError) as error:
            await _page_html(page)
    elapsed = asyncio.get_running_loop().time() - started
    assert error.value.code == "PAGE_CONTENT_UNAVAILABLE"
    assert 9.5 <= elapsed < 11.5
    assert page.calls > 1
    assert page.cancelled is hang


@pytest.mark.asyncio
async def test_evaluate_cancellation_propagates_and_cancels_pending_call() -> None:
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class HangingPage:
        async def evaluate(self, expression: str) -> str:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
            return ""

    task = asyncio.create_task(_page_html(HangingPage()))
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_evaluate_error_does_not_expose_raw_detail_in_traceback() -> None:
    class FailingPage:
        async def evaluate(self, expression: str) -> str:
            raise RuntimeError("synthetic-private-page-detail")

    with pytest.raises(RunnerError) as error:
        await _page_html(FailingPage())
    assert error.value.code == "PAGE_CONTENT_UNAVAILABLE"
    assert "synthetic-private-page-detail" not in "".join(traceback.format_exception(error.value))


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["False", "True", "READY:", None, 1])
async def test_evaluate_rejects_serialized_booleans_and_invalid_snapshots(value: object) -> None:
    class InvalidPage:
        async def evaluate(self, expression: str) -> object:
            return value

    with pytest.raises(RunnerError) as error:
        await _page_html(InvalidPage())
    assert error.value.code == "PAGE_CONTENT_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("getter", ["get_content", "content"])
async def test_existing_content_getters_take_precedence_over_evaluate(getter: str) -> None:
    class GetterPage:
        async def evaluate(self, expression: str) -> str:
            pytest.fail("Existing content getter must retain precedence")

    page = GetterPage()
    setattr(page, getter, lambda: TEACHING_HTML)
    assert await _page_html(page) == TEACHING_HTML
