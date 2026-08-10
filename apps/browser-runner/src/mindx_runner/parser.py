import re
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(frozen=True)
class StudentRow:
    student_id: str | None
    full_name: str
    discriminator: str | None


class _StudentRowParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[StudentRow] = []
        self._active: dict[str, str | None] | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if "data-student-id" in attributes or "data-discriminator" in attributes:
            self._active = {
                "student_id": attributes.get("data-student-id"),
                "discriminator": attributes.get("data-discriminator"),
            }
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._active is None or tag not in {"div", "li", "tr"}:
            return
        full_name = re.sub(r"\s+", " ", "".join(self._text)).strip()
        if full_name:
            self.rows.append(
                StudentRow(
                    student_id=self._active["student_id"],
                    full_name=full_name,
                    discriminator=self._active["discriminator"],
                )
            )
        self._active = None
        self._text = []


def parse_student_rows(html: str) -> list[StudentRow]:
    parser = _StudentRowParser()
    parser.feed(html)
    parser.close()
    return parser.rows


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def resolve_student(
    rows: list[StudentRow],
    *,
    student_id: str | None = None,
    full_name: str | None = None,
    discriminator: str | None = None,
) -> StudentRow:
    if student_id:
        matches = [row for row in rows if row.student_id == student_id]
    elif discriminator:
        matches = [row for row in rows if row.discriminator == discriminator]
    elif full_name:
        matches = [row for row in rows if _normalize(row.full_name) == _normalize(full_name)]
    else:
        matches = []

    if len(matches) == 1 and (matches[0].student_id or matches[0].discriminator):
        return matches[0]
    raise RuntimeError("Student identity is unresolvable")
