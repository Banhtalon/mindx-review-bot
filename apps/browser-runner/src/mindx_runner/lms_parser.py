import hashlib
from collections.abc import Collection
from datetime import date, time
from html.parser import HTMLParser
from typing import NoReturn

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
        self.invalid_context_nesting = False
        self.invalid_row_identity = False
        self._element_stack: list[tuple[int, str]] = []
        self._next_element_id = 0
        self._context_element_id: int | None = None

        self.rows: list[dict[str, str | None]] = []
        self._active_row: dict[str, str | None] | None = None
        self._row_element_id: int | None = None
        self._row_text: list[str] = []
        self.incomplete_row = False

    def _open_element(self, tag: str) -> int | None:
        if tag in _VOID_TAGS:
            return None
        self._next_element_id += 1
        element_id = self._next_element_id
        self._element_stack.append((element_id, tag))
        return element_id

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        normalized_tag = tag.lower()
        element_id = self._open_element(normalized_tag)

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
            if element_id is None:
                self.invalid_context_nesting = True
            else:
                self._context_element_id = element_id
            return

        if (
            self._active_row is None
            and self._context_element_id is not None
            and attributes.get("data-lms-student") == "true"
        ):
            if element_id is None:
                self.invalid_context_nesting = True
                return
            student_id = attributes.get("data-student-id")
            discriminator = attributes.get("data-discriminator")
            if ("data-student-id" in attributes and not _has_non_blank_value(student_id)) or (
                "data-discriminator" in attributes and not _has_non_blank_value(discriminator)
            ):
                self.invalid_row_identity = True
                return
            self._active_row = {
                "student-id": student_id,
                "discriminator": discriminator,
                "attendance": attributes.get("data-attendance"),
            }
            self._row_element_id = element_id
            self._row_text = []

    def handle_data(self, data: str) -> None:
        if self._active_row is not None:
            self._row_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in _VOID_TAGS:
            return

        if not self._element_stack or self._element_stack[-1][1] != normalized_tag:
            if self._context_element_id is not None:
                self.invalid_context_nesting = True
            return

        element_id, _ = self._element_stack.pop()
        if self._active_row is not None and element_id == self._row_element_id:
            self._active_row["full-name"] = "".join(self._row_text)
            self.rows.append(self._active_row)
            self._active_row = None
            self._row_element_id = None
            self._row_text = []

        if element_id == self._context_element_id:
            if self._active_row is not None:
                self.invalid_context_nesting = True
            self._context_element_id = None

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def close(self) -> None:
        super().close()
        self.incomplete_context = (
            self.context is not None and self._context_element_id is not None
        )
        self.incomplete_row = self._active_row is not None


def _required(record: dict[str, str | None], name: str) -> str:
    value = record.get(name)
    if value is None or not value.strip():
        raise LmsParserError("LMS_DATA_INVALID")
    return value


def _has_non_blank_value(value: str | None) -> bool:
    return value is not None and bool(value.strip())


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


def _parse_lms_page_impl(
    html: str,
    allowed_class_codes: Collection[str],
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
        or parser.invalid_context_nesting
        or parser.invalid_row_identity
    ):
        raise LmsParserError("LMS_DATA_INVALID")

    allowed_codes = _normalize_catalog(allowed_class_codes)
    if not allowed_codes:
        raise LmsParserError("LMS_CLASS_CATALOG_UNAVAILABLE")

    seen_student_ids: set[str] = set()
    seen_discriminators: set[str] = set()
    rows: list[LmsRosterRow] = []
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

    if not rows:
        raise LmsParserError("LMS_DATA_INVALID")

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

    if page.class_code not in allowed_codes:
        raise LmsParserError("LMS_UNKNOWN_CLASS_CODE")
    return page


def _raise_public_error(code: str) -> NoReturn:
    raise LmsParserError(code) from None


def parse_lms_page(
    html: str,
    *,
    allowed_class_codes: Collection[str] = DEFAULT_SYNTHETIC_CLASS_CODES,
) -> LmsPageExtract:
    try:
        return _parse_lms_page_impl(html, allowed_class_codes)
    except LmsParserError as error:
        error_code = error.code
    except (TypeError, ValueError, ValidationError):
        error_code = "LMS_DATA_INVALID"

    html = ""
    allowed_class_codes = ()
    _raise_public_error(error_code)
