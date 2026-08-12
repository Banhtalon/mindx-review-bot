import hashlib
import re
from collections.abc import Collection
from datetime import date, time
from html.parser import HTMLParser

from pydantic import ValidationError

from .teaching_models import TeachingBatchExtract, TeachingSessionExtract

DEFAULT_SYNTHETIC_CLASS_CODES = frozenset({"SYN-ROBOTICS-01", "SYN-JS-02"})


class TeachingParserError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _TeachingSessionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.records: list[dict[str, str | None]] = []
        self._active: dict[str, str | None] | None = None
        self._active_tag: str | None = None
        self._active_depth = 0
        self._text: list[str] = []
        self.page_state: str | None = None
        self.schedule_marker = False
        self.empty_marker = False
        self.login_marker = False
        self.incomplete_session = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("data-page-state"):
            self.page_state = attributes["data-page-state"]
        if attributes.get("data-teaching-schedule") == "true":
            self.schedule_marker = True
        if attributes.get("data-empty-state") == "true":
            self.empty_marker = True
        if attributes.get("data-teaching-login") == "true":
            self.login_marker = True

        normalized_tag = tag.lower()
        if self._active is None and attributes.get("data-teaching-session") == "true":
            self._active = {
                key.removeprefix("data-"): value
                for key, value in attributes.items()
                if key.startswith("data-")
                and key.removeprefix("data-")
                in {
                    "class-code",
                    "source-session-id",
                    "session-number",
                    "session-type",
                    "scheduled-date",
                    "start-time",
                    "end-time",
                    "teacher-name",
                }
            }
            self._active_tag = normalized_tag
            self._active_depth = 0
            self._text = []
        elif self._active is not None and normalized_tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self._active_depth += 1

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._active is None:
            return
        normalized_tag = tag.lower()
        if self._active_depth > 0:
            self._active_depth -= 1
            return
        if normalized_tag != self._active_tag:
            return
        self._active["text"] = re.sub(r"\s+", " ", "".join(self._text)).strip()
        self.records.append(self._active)
        self._active = None
        self._active_tag = None
        self._active_depth = 0
        self._text = []

    def close(self) -> None:
        super().close()
        self.incomplete_session = self._active is not None


def _required(record: dict[str, str | None], name: str) -> str:
    value = record.get(name)
    if value is None or not value.strip():
        raise TeachingParserError("TEACHING_DATA_INVALID")
    return value


def _optional_int(record: dict[str, str | None], name: str) -> int | None:
    value = record.get(name)
    if value is None or not value.strip():
        return None
    return int(value)


def parse_teaching_schedule(
    html: str,
    *,
    allowed_class_codes: Collection[str] = DEFAULT_SYNTHETIC_CLASS_CODES,
) -> TeachingBatchExtract:
    source_page_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    parser = _TeachingSessionParser()
    parser.feed(html)
    parser.close()

    if parser.login_marker or parser.page_state == "login":
        raise TeachingParserError("TEACHING_LOGIN_REQUIRED")
    if parser.incomplete_session or not parser.schedule_marker:
        raise TeachingParserError("TEACHING_DATA_INVALID")
    allowed_codes = {code.strip().upper() for code in allowed_class_codes}
    if not allowed_codes:
        raise TeachingParserError("TEACHING_CLASS_CATALOG_UNAVAILABLE")

    sessions: list[TeachingSessionExtract] = []
    source_ids: set[str] = set()
    try:
        for record in parser.records:
            session = TeachingSessionExtract(
                class_code=_required(record, "class-code"),
                source_session_id=record.get("source-session-id"),
                session_number=_optional_int(record, "session-number"),
                session_type=record.get("session-type"),
                scheduled_date=date.fromisoformat(_required(record, "scheduled-date")),
                start_time=time.fromisoformat(_required(record, "start-time")),
                end_time=time.fromisoformat(_required(record, "end-time")),
                teacher_name=record.get("teacher-name"),
            )
            if session.class_code not in allowed_codes:
                raise TeachingParserError("TEACHING_UNKNOWN_CLASS_CODE")
            source_id = session.source_session_id
            if source_id is not None and source_id in source_ids:
                raise TeachingParserError("TEACHING_DUPLICATE_SOURCE_ID")
            if source_id is not None:
                source_ids.add(source_id)
            sessions.append(session)
    except TeachingParserError:
        raise
    except (TypeError, ValueError, ValidationError) as error:
        raise TeachingParserError("TEACHING_DATA_INVALID") from error

    if not sessions and not parser.empty_marker:
        raise TeachingParserError("TEACHING_DATA_INVALID")
    warnings = ["TEACHING_SCHEDULE_EMPTY"] if not sessions else []
    if parser.empty_marker and sessions:
        raise TeachingParserError("TEACHING_DATA_INVALID")
    return TeachingBatchExtract(
        sessions=sessions,
        source_page_hash=source_page_hash,
        warnings=warnings,
    )
