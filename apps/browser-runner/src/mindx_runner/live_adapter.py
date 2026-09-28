"""Small, deterministic, read-only Teaching/LMS site adapter."""

import inspect
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

from .cli import RunnerError
from .lms_models import LmsPageExtract
from .lms_parser import LmsParserError, parse_lms_page
from .network_guard import classify_request
from .teaching_models import TeachingBatchExtract
from .teaching_parser import TeachingParserError, parse_teaching_schedule


def _payload_mapping(payload: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    return payload


def _read_string(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    return value.strip()


def _read_login_paths(payload: Mapping[str, object]) -> tuple[str, ...]:
    raw = payload.get("login_paths", ())
    if raw is None:
        return ()
    if isinstance(raw, str | bytes) or not isinstance(raw, Sequence):
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    paths: list[str] = []
    for path in raw:
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or "?" in path
            or "#" in path
            or not path.strip()
        ):
            raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
        paths.append(path)
    return tuple(dict.fromkeys(paths))


def _read_url(job_type: str, payload: Mapping[str, object], login_paths: Collection[str]) -> str:
    key = "teaching_url" if job_type == "sync_teaching" else "lms_url"
    url = next(
        (
            _read_string(payload, candidate)
            for candidate in (key, "read_url", "page_url", "target_url", "url")
            if candidate in payload
        ),
        None,
    )
    if url is None:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")

    parsed = urlparse(url)
    expected_host = "teachingmindx.top" if job_type == "sync_teaching" else "lms.mindx.edu.vn"
    try:
        port = parsed.port
    except ValueError as error:
        raise RunnerError("DOMAIN_BLOCKED") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != expected_host
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or bool(parsed.fragment)
        or "#" in url
    ):
        raise RunnerError("DOMAIN_BLOCKED")
    allowed_urls = payload.get("allowed_urls")
    if allowed_urls is not None:
        if isinstance(allowed_urls, str | bytes) or not isinstance(allowed_urls, Sequence):
            raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
        if any(
            not isinstance(candidate, str) or not candidate.strip()
            for candidate in allowed_urls
        ):
            raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
        if url not in allowed_urls:
            raise RunnerError("DOMAIN_BLOCKED")
    allowed_paths = payload.get("allowed_paths")
    if allowed_paths is not None:
        if isinstance(allowed_paths, str | bytes) or not isinstance(allowed_paths, Sequence):
            raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
        if any(
            not isinstance(path, str) or not path.startswith("/") or "?" in path or "#" in path
            for path in allowed_paths
        ):
            raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
        if parsed.path not in allowed_paths:
            raise RunnerError("DOMAIN_BLOCKED")
    decision = classify_request("GET", url, login_paths=login_paths)
    if not decision.allowed:
        raise RunnerError(decision.code)
    return url


def _allowed_class_codes(payload: Mapping[str, object]) -> tuple[str, ...]:
    raw = payload.get("allowed_class_codes", ())
    if isinstance(raw, str | bytes) or not isinstance(raw, Sequence):
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    codes = tuple(code.strip() for code in raw if isinstance(code, str) and code.strip())
    if len(codes) != len(raw) or not codes:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    return tuple(dict.fromkeys(codes))


def _expected_int(payload: Mapping[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if type(value) is not int or value < 1:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    return value


async def _page_html(page: object) -> str:
    getter = getattr(page, "get_content", None)
    if getter is None:
        getter = getattr(page, "content", None)
    if getter is None:
        evaluator = getattr(page, "evaluate", None)
        if callable(evaluator):
            def read_html() -> object:
                return evaluator("() => document.documentElement.outerHTML")

            getter = read_html
    if getter is None:
        raise RunnerError("PAGE_CONTENT_UNAVAILABLE")
    try:
        value = getter() if callable(getter) else getter
        if inspect.isawaitable(value):
            value = await value
    except Exception as error:
        raise RunnerError("PAGE_CONTENT_UNAVAILABLE") from error
    if not isinstance(value, str) or not value:
        raise RunnerError("PAGE_CONTENT_UNAVAILABLE")
    return value


_ALLOWED_CONTEXT_FIELDS: Final[frozenset[str]] = frozenset(
    {"class_code", "session_number", "source_session_id"}
)


def _context_string(context: Mapping[str, object], key: str) -> str | None:
    if key not in context:
        return None
    value = context[key]
    if not isinstance(value, str) or not value.strip():
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    return value.strip()


def _context_int(context: Mapping[str, object], key: str) -> int | None:
    if key not in context:
        return None
    value = context[key]
    if type(value) is not int or value < 1:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    return value


@dataclass(frozen=True, slots=True)
class _ExpectedContext:
    class_code: str | None = None
    session_number: int | None = None
    source_session_id: str | None = None


def _validate_context(job_type: str, payload: Mapping[str, object]) -> _ExpectedContext:
    payload = _payload_mapping(payload)
    direct_class = _read_string(payload, "expected_class_code")
    if direct_class is not None:
        direct_class = direct_class.upper()
    direct_session = _expected_int(payload, "expected_session_number")
    direct_source = _read_string(payload, "expected_source_session_id")

    if job_type != "sync_teaching":
        if "expected_context" in payload or "context" in payload:
            raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
        return _ExpectedContext(
            class_code=direct_class,
            session_number=direct_session,
            source_session_id=direct_source,
        )

    has_expected = "expected_context" in payload
    has_context = "context" in payload
    if has_expected and has_context:
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")

    if not has_expected and not has_context:
        return _ExpectedContext(
            class_code=direct_class,
            session_number=direct_session,
            source_session_id=direct_source,
        )

    raw_context = payload["expected_context" if has_expected else "context"]
    if not isinstance(raw_context, Mapping):
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")

    for key in raw_context:
        if not isinstance(key, str) or key not in _ALLOWED_CONTEXT_FIELDS:
            raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")

    context_class = _context_string(raw_context, "class_code")
    if context_class is not None:
        context_class = context_class.upper()
    context_session = _context_int(raw_context, "session_number")
    context_source = _context_string(raw_context, "source_session_id")

    return _ExpectedContext(
        class_code=direct_class if direct_class is not None else context_class,
        session_number=direct_session if direct_session is not None else context_session,
        source_session_id=direct_source if direct_source is not None else context_source,
    )


def _check_teaching_context(
    context_or_payload: _ExpectedContext | Mapping[str, object],
    batch: TeachingBatchExtract,
) -> int:
    context = (
        context_or_payload
        if isinstance(context_or_payload, _ExpectedContext)
        else _validate_context("sync_teaching", context_or_payload)
    )
    expected_class = context.class_code
    expected_session = context.session_number
    expected_source = context.source_session_id
    sessions = getattr(batch, "sessions", ())
    class_matches = [
        session for session in sessions
        if expected_class is None or session.class_code == expected_class
    ]
    if expected_class is not None and not class_matches:
        raise RunnerError("CLASS_IDENTITY_MISMATCH")
    matches = [
        session for session in class_matches
        if expected_session is None or session.session_number == expected_session
    ]
    if expected_session is not None and not matches:
        raise RunnerError("SESSION_IDENTITY_MISMATCH")
    if expected_source is not None:
        source_matches = [
            session for session in sessions
            if session.source_session_id == expected_source
        ]
        if len(source_matches) != 1:
            raise RunnerError("SESSION_IDENTITY_MISMATCH")
        matches = [
            session for session in matches
            if session.source_session_id == expected_source
        ]
    if (
        expected_class is not None
        or expected_session is not None
        or expected_source is not None
    ):
        if len(matches) != 1:
            raise RunnerError("SESSION_IDENTITY_MISMATCH")
        return 1
    return len(sessions)


def _check_lms_context(
    context_or_payload: _ExpectedContext | Mapping[str, object],
    page: LmsPageExtract,
) -> int:
    context = (
        context_or_payload
        if isinstance(context_or_payload, _ExpectedContext)
        else _validate_context("read_lms_pending", context_or_payload)
    )
    expected_class = context.class_code
    expected_session = context.session_number
    expected_source = context.source_session_id
    if expected_class is not None and page.class_code != expected_class:
        raise RunnerError("CLASS_IDENTITY_MISMATCH")
    if expected_session is not None and page.session_number != expected_session:
        raise RunnerError("SESSION_IDENTITY_MISMATCH")
    if expected_source is not None and page.source_session_id != expected_source:
        raise RunnerError("SESSION_IDENTITY_MISMATCH")
    return len(page.rows)


async def readonly_site_adapter(config: object, claimed: object, browser: object) -> int:
    """Read one explicitly configured page and return validated record count.

    The adapter never submits forms, calls a write endpoint, or returns page
    content. All HTML is consumed by deterministic parsers immediately.
    """

    job_type = getattr(config, "job_type", None)
    claimed_type = getattr(claimed, "job_type", None)
    if job_type not in {"sync_teaching", "read_lms_pending"} or claimed_type != job_type:
        raise RunnerError("JOB_TYPE_MISMATCH")
    payload = _payload_mapping(getattr(claimed, "payload", {}))
    login_paths = _read_login_paths(payload)
    configure = getattr(browser, "configure_login_paths", None)
    if configure is not None:
        if not callable(configure):
            raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
        configure(login_paths)
    url = _read_url(job_type, payload, login_paths)
    codes = _allowed_class_codes(payload)
    context = _validate_context(job_type, payload)
    open_page = getattr(browser, "open", None)
    if not callable(open_page):
        raise RunnerError("SITE_ADAPTER_NOT_CONFIGURED")
    try:
        page = open_page(url)
        if inspect.isawaitable(page):
            page = await page
    except RunnerError:
        raise
    except Exception as error:
        code = getattr(error, "code", None)
        if isinstance(code, str) and code:
            raise RunnerError(code) from error
        raise RunnerError("BROWSER_NAVIGATION_FAILED") from error
    html = await _page_html(page)

    try:
        if job_type == "sync_teaching":
            batch = parse_teaching_schedule(html, allowed_class_codes=codes)
            return _check_teaching_context(context, batch)
        parsed = parse_lms_page(html, allowed_class_codes=codes)
        return _check_lms_context(context, parsed)
    except RunnerError:
        raise
    except (TeachingParserError, LmsParserError) as error:
        raise RunnerError(error.code) from None
