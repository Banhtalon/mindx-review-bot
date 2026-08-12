import hashlib
from collections.abc import Collection
from datetime import date, time
from html.parser import HTMLParser

from pydantic import ValidationError

from .lms_models import LmsPageExtract, LmsRosterRow

DEFAULT_SYNTHETIC_CLASS_CODES = frozenset({"SYN-CLASS-01"})
_VOID_TAGS = frozenset(
    {
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
    }
)
_ALLOWED_ATTENDANCE = frozenset({"present", "online", "absent", "unknown"})


class LmsParserError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _LmsPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.context: dict[str, str | None] | None = None
        self.page_state: str | None = None
        self.context_marker = False
        self.incomplete_context = False
        self._context_tag: str | None = None
        self._context_depth = 0

        self.rows: list[dict[str, str | None]] = []
        self._active_row: dict[str, str | None] | None = None
        self._row_tag: str | None = None
        self._row_depth = 0
        self._row_text: list[str] = []
        self.incomplete_row = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        normalized_tag = tag.lower()

        if attributes.get("data-page-state"):
            self.page_state = attributes["data-page-state"]

        if self.context is None and attributes.get("data-lms-context") == "true":
            self.context_marker = True
            self.context = {
                key.removeprefix("data-"): value
                for key, value in attributes.items()
                if key.startswith("data-")
                and key.removeprefix("data-")
                in {
                    "class-code",
                    "session-number",
                    "scheduled-date",
                    "start-time",
                    "end-time",
                    "source-session-id",
                    "lesson",
                    "homework",
                }
            }
            self._context_tag = normalized_tag
            self._context_depth = 0
            return

        if self._active_row is None and attributes.get("data-lms-student") == "true":
            self._active_row = {
                "student-id": attributes.get("data-student-id"),
                "discriminator": attributes.get("data-discriminator"),
                "attendance": attributes.get("data-attendance"),
            }
            self._row_tag = normalized_tag
            self._row_depth = 0
            self._row_text = []
            return

        if (
            self.context is not None
            and self._context_tag is not None
            and normalized_tag not in _VOID_TAGS
        ):
            self._context_depth += 1
        if self._active_row is not None and normalized_tag not in _VOID_TAGS:
            self._row_depth += 1

    def handle_data(self, data: str) -> None:
        if self._active_row is not None:
            self._row_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()

        if self._active_row is not None:
            if self._row_depth > 0:
                self._row_depth -= 1
            elif normalized_tag == self._row_tag:
                self._active_row["full-name"] = "".join(self._row_text)
                self.rows.append(self._active_row)
                self._active_row = None
                self._row_tag = None
                self._row_depth = 0
                self._row_text = []

        if self.context is not None and self._context_tag is not None:
            if self._context_depth > 0:
                self._context_depth -= 1
            elif normalized_tag == self._context_tag:
                self._context_tag = None

    def close(self) -> None:
        super().close()
        self.incomplete_context = self.context is not None and self._context_tag is not None
        self.incomplete_row = self._active_row is not None


def _required(record: dict[str, str | None], name: str) -> str:
    value = record.get(name)
    if value is None or not value.strip():
        raise LmsParserError("LMS_DATA_INVALID")
    return value


def _optional_int(record: dict[str, str | None], name: str) -> int | None:
    value = record.get(name)
    if value is None or not value.strip():
        return None
    return int(value)


def _normalize_catalog(codes: Collection[str]) -> set[str]:
    normalized: set[str] = set()
    for code in codes:
        cleaned = " ".join(code.split()).strip()
        if cleaned:
            normalized.add(cleaned)
    return normalized


def parse_lms_page(
    html: str,
    *,
    allowed_class_codes: Collection[str] = DEFAULT_SYNTHETIC_CLASS_CODES,
) -> LmsPageExtract:
    source_page_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    parser = _LmsPageParser()
    parser.feed(html)
    parser.close()

    if parser.page_state == "login":
        raise LmsParserError("LMS_LOGIN_REQUIRED")
    if (
        not parser.context_marker
        or parser.context is None
        or parser.incomplete_context
        or parser.incomplete_row
    ):
        raise LmsParserError("LMS_DATA_INVALID")

    allowed_codes = _normalize_catalog(allowed_class_codes)
    if not allowed_codes:
        raise LmsParserError("LMS_CLASS_CATALOG_UNAVAILABLE")

    seen_student_ids: set[str] = set()
    seen_discriminators: set[str] = set()
    rows: list[LmsRosterRow] = []
    try:
        for record in parser.rows:
            attendance = record.get("attendance") or "unknown"
            if attendance not in _ALLOWED_ATTENDANCE:
                raise LmsParserError("LMS_DATA_INVALID")

            row = LmsRosterRow(
                student_id=record.get("student-id"),
                discriminator=record.get("discriminator"),
                full_name=_required(record, "full-name"),
                attendance=attendance,  # type: ignore[arg-type]
            )
            if row.student_id is not None:
                if row.student_id in seen_student_ids:
                    raise LmsParserError("LMS_DUPLICATE_STUDENT_ID")
                seen_student_ids.add(row.student_id)
            if row.discriminator is not None:
                if row.discriminator in seen_discriminators:
                    raise LmsParserError("LMS_DUPLICATE_DISCRIMINATOR")
                seen_discriminators.add(row.discriminator)
            rows.append(row)

        page = LmsPageExtract(
            class_code=_required(parser.context, "class-code"),
            session_number=int(_required(parser.context, "session-number")),
            scheduled_date=date.fromisoformat(_required(parser.context, "scheduled-date")),
            start_time=time.fromisoformat(_required(parser.context, "start-time")),
            end_time=time.fromisoformat(_required(parser.context, "end-time")),
            source_session_id=parser.context.get("source-session-id"),
            rows=tuple(rows),
            lesson=_required(parser.context, "lesson"),
            homework=parser.context.get("homework"),
            source_page_hash=source_page_hash,
            warnings=(),
        )
    except LmsParserError:
        raise
    except (TypeError, ValueError, ValidationError) as error:
        raise LmsParserError("LMS_DATA_INVALID") from error

    if page.class_code not in allowed_codes:
        raise LmsParserError("LMS_UNKNOWN_CLASS_CODE")
    return page
