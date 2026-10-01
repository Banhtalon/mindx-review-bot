import hashlib
import re
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date, datetime, time
from html.parser import HTMLParser

from pydantic import ValidationError

from .teaching_models import TeachingBatchExtract, TeachingSessionExtract

DEFAULT_SYNTHETIC_CLASS_CODES = frozenset({"SYN-ROBOTICS-01", "SYN-JS-02"})
_LIVE_DATE_PATTERN = re.compile(r"\b(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})\b")
_LIVE_TIME_PATTERN = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?)"
)


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
                    "block",
                    "special-event",
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


@dataclass(slots=True)
class _LiveNode:
    tag: str
    attrs: dict[str, str]
    children: list["_LiveNode | str"] = field(default_factory=list)


class _LiveTeachingDomParser(HTMLParser):
    """Build the small DOM slice needed by Teaching's live schedule table."""

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

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _LiveNode("root", {})
        self._stack = [self.root]
        self.malformed = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _LiveNode(tag.lower(), {key: value or "" for key, value in attrs})
        self._stack[-1].children.append(node)
        if node.tag not in self._VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self._stack[-1].tag == tag.lower():
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if len(self._stack) == 1 or self._stack[-1].tag != normalized_tag:
            self.malformed = True
            return
        self._stack.pop()

    def close(self) -> None:
        super().close()
        self.malformed = self.malformed or len(self._stack) != 1


def _live_text(node: _LiveNode) -> str:
    return "".join(
        child if isinstance(child, str) else _live_text(child) for child in node.children
    )


def _live_descendants(node: _LiveNode, tag: str | None = None) -> list[_LiveNode]:
    matches: list[_LiveNode] = []
    for child in node.children:
        if not isinstance(child, _LiveNode):
            continue
        if tag is None or child.tag == tag:
            matches.append(child)
        matches.extend(_live_descendants(child, tag))
    return matches


def _live_direct_cells(row: _LiveNode) -> list[_LiveNode]:
    return [
        child
        for child in row.children
        if isinstance(child, _LiveNode) and child.tag in {"th", "td"}
    ]


def _live_has_class(node: _LiveNode, class_name: str) -> bool:
    return class_name in node.attrs.get("class", "").split()


def _live_clock(value: str) -> time:
    try:
        format_string = "%H:%M:%S" if value.count(":") == 2 else "%H:%M"
        return datetime.strptime(value, format_string).time()
    except ValueError as error:
        raise TeachingParserError("TEACHING_DATA_INVALID") from error


def _live_schedule_records(
    html: str, allowed_codes: Collection[str]
) -> tuple[list[dict[str, str | None]], bool]:
    parser = _LiveTeachingDomParser()
    parser.feed(html)
    parser.close()
    if parser.malformed:
        raise TeachingParserError("TEACHING_DATA_INVALID")

    for table in _live_descendants(parser.root, "table"):
        rows = _live_descendants(table, "tr")
        if not rows:
            continue
        header_cells = _live_direct_cells(rows[0])
        if len(header_cells) < 2:
            continue
        if any(
            cell.attrs.get("colspan", "1") != "1"
            or cell.attrs.get("rowspan", "1") != "1"
            for cell in header_cells
        ):
            raise TeachingParserError("TEACHING_DATA_INVALID")
        dates: list[date | None] = []
        for cell in header_cells:
            match = _LIVE_DATE_PATTERN.search(_live_text(cell))
            if match is None:
                dates.append(None)
                continue
            try:
                dates.append(datetime.strptime(match.group(0), "%d/%m/%Y").date())
            except ValueError as error:
                raise TeachingParserError("TEACHING_DATA_INVALID") from error
        if sum(value is not None for value in dates) < 1:
            continue

        records: list[dict[str, str | None]] = []
        for row in rows[1:]:
            cells = _live_direct_cells(row)
            if not cells:
                continue
            target_in_row = any(
                len(code_nodes := [
                    node
                    for node in _live_descendants(session_node)
                    if _live_has_class(node, "class-code")
                ])
                == 1
                and _live_text(code_nodes[0]).strip().upper() in allowed_codes
                for session_node in _live_descendants(row)
                if _live_has_class(session_node, "regular-class")
            )
            if not target_in_row:
                continue
            row_time_matches = list(_LIVE_TIME_PATTERN.finditer(_live_text(cells[0])))
            if len(row_time_matches) != 1:
                raise TeachingParserError("TEACHING_DATA_INVALID")
            time_match = row_time_matches[0]
            row_start = _live_clock(time_match.group("start"))
            row_end = _live_clock(time_match.group("end"))
            if len(cells) != len(header_cells) or any(
                cell.attrs.get("colspan", "1") != "1"
                or cell.attrs.get("rowspan", "1") != "1"
                for cell in cells
            ):
                raise TeachingParserError("TEACHING_DATA_INVALID")
            for index, cell in enumerate(cells[1:], start=1):
                scheduled_date = dates[index] if index < len(dates) else None
                if scheduled_date is None:
                    if _live_descendants(cell):
                        raise TeachingParserError("TEACHING_DATA_INVALID")
                    continue
                for session_node in _live_descendants(cell):
                    if not _live_has_class(session_node, "regular-class"):
                        continue
                    code_nodes = [
                        node
                        for node in _live_descendants(session_node)
                        if _live_has_class(node, "class-code")
                    ]
                    if len(code_nodes) != 1:
                        continue
                    class_code = _live_text(code_nodes[0]).strip().upper()
                    if class_code not in allowed_codes:
                        continue
                    attributes = session_node.attrs
                    inner_times = list(_LIVE_TIME_PATTERN.finditer(_live_text(session_node)))
                    if len(inner_times) > 1:
                        raise TeachingParserError("TEACHING_DATA_INVALID")
                    session_start = row_start
                    session_end = row_end
                    if inner_times:
                        session_start = _live_clock(inner_times[0].group("start"))
                        session_end = _live_clock(inner_times[0].group("end"))
                        if (
                            session_start < row_start
                            or session_end > row_end
                            or session_end <= session_start
                        ):
                            raise TeachingParserError("TEACHING_DATA_INVALID")
                    records.append(
                        {
                            "class-code": class_code,
                            "source-session-id": attributes.get("data-source-session-id") or None,
                            "session-number": attributes.get("data-session-number") or None,
                            "session-type": "regular",
                            "scheduled-date": scheduled_date.isoformat(),
                            "start-time": session_start.isoformat(),
                            "end-time": session_end.isoformat(),
                            "block": attributes.get("data-block") or None,
                            "special-event": attributes.get("data-special-event") or None,
                            "teacher-name": None,
                        }
                    )
        return records, True
    return [], False


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
    if parser.incomplete_session:
        raise TeachingParserError("TEACHING_DATA_INVALID")
    allowed_codes = {code.strip().upper() for code in allowed_class_codes}
    if not allowed_codes:
        raise TeachingParserError("TEACHING_CLASS_CATALOG_UNAVAILABLE")

    if parser.schedule_marker:
        records = parser.records
        live_schedule = False
    else:
        try:
            records, live_schedule = _live_schedule_records(html, allowed_codes)
        except RecursionError as error:
            raise TeachingParserError("TEACHING_DATA_INVALID") from error
    if not parser.schedule_marker and not live_schedule:
        raise TeachingParserError("TEACHING_DATA_INVALID")
    sessions: list[TeachingSessionExtract] = []
    source_ids: set[str] = set()
    semantic_ids: set[tuple[str, date, int | None, time, time]] = set()
    try:
        for record in records:
            raw_class_code = _required(record, "class-code")
            class_code = TeachingSessionExtract.normalize_class_code(raw_class_code)
            if class_code not in allowed_codes:
                continue
            session = TeachingSessionExtract(
                class_code=class_code,
                source_session_id=record.get("source-session-id"),
                session_number=_optional_int(record, "session-number"),
                session_type=record.get("session-type"),
                scheduled_date=date.fromisoformat(_required(record, "scheduled-date")),
                start_time=time.fromisoformat(_required(record, "start-time")),
                end_time=time.fromisoformat(_required(record, "end-time")),
                block=record.get("block"),
                special_event=record.get("special-event"),
                teacher_name=record.get("teacher-name"),
            )
            source_id = session.source_session_id
            if source_id is not None and source_id in source_ids:
                raise TeachingParserError("TEACHING_DUPLICATE_SOURCE_ID")
            if source_id is not None:
                source_ids.add(source_id)
            semantic_id = (
                session.class_code,
                session.scheduled_date,
                session.session_number,
                session.start_time,
                session.end_time,
            )
            if semantic_id in semantic_ids:
                raise TeachingParserError("TEACHING_DUPLICATE_SOURCE_ID")
            semantic_ids.add(semantic_id)
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
