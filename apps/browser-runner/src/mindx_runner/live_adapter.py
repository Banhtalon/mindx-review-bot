"""Small, deterministic, read-only Teaching/LMS site adapter."""

import inspect
from collections.abc import Collection, Mapping, Sequence
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


def _check_teaching_context(
    payload: Mapping[str, object],
    batch: TeachingBatchExtract,
) -> int:
    expected_class = _read_string(payload, "expected_class_code")
    if expected_class is not None:
        expected_class = expected_class.upper()
    expected_session = _expected_int(payload, "expected_session_number")
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
    if expected_class is not None or expected_session is not None:
        if len(matches) != 1:
            raise RunnerError("SESSION_IDENTITY_MISMATCH")
        return 1
    return len(sessions)


def _check_lms_context(payload: Mapping[str, object], page: LmsPageExtract) -> int:
    expected_class = _read_string(payload, "expected_class_code")
    if expected_class is not None:
        expected_class = expected_class.upper()
    expected_session = _expected_int(payload, "expected_session_number")
    expected_source = _read_string(payload, "expected_source_session_id")
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
        raise RunnerError("DOMAIN_BLOCKED") from error
    html = await _page_html(page)

    try:
        if job_type == "sync_teaching":
            batch = parse_teaching_schedule(html, allowed_class_codes=codes)
            return _check_teaching_context(payload, batch)
        parsed = parse_lms_page(html, allowed_class_codes=codes)
        return _check_lms_context(payload, parsed)
    except RunnerError:
        raise
    except (TeachingParserError, LmsParserError) as error:
        raise RunnerError(error.code) from None
