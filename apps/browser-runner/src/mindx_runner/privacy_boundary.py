import re
from html import escape
from html.parser import HTMLParser

ROSTER_MARKER = re.compile(
    r"data-student-id|data-discriminator|data-roster|id=[\"']roster[\"']",
    re.IGNORECASE,
)
UNSAFE_ROSTER_TAGS = frozenset(
    {"table", "thead", "tbody", "tfoot", "tr", "td", "th", "ul", "ol", "li"}
)
SESSION_NUMBER = re.compile(r"[0-9]+")


class _NavigationContextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.class_codes: list[str] = []
        self.session_numbers: list[str] = []
        self.has_unsafe_roster_markup = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in UNSAFE_ROSTER_TAGS:
            self.has_unsafe_roster_markup = True

        attributes = dict(attrs)
        if "data-class-code" in attributes and attributes["data-class-code"]:
            self.class_codes.append(attributes["data-class-code"] or "")
        if "data-session-number" in attributes and attributes["data-session-number"]:
            self.session_numbers.append(attributes["data-session-number"] or "")


def assert_agent_page_safe(page_html: str) -> str:
    if ROSTER_MARKER.search(page_html):
        raise RuntimeError("Navigation agent cannot receive roster page")

    parser = _NavigationContextParser()
    parser.feed(page_html)
    parser.close()

    if parser.has_unsafe_roster_markup:
        raise RuntimeError("Navigation page contains unsafe roster markup")
    if len(parser.class_codes) != 1 or len(parser.session_numbers) != 1:
        raise RuntimeError("Navigation page identity is unresolvable")

    class_code = parser.class_codes[0]
    session_number = parser.session_numbers[0]
    if not SESSION_NUMBER.fullmatch(session_number):
        raise RuntimeError("Navigation page identity is unresolvable")

    return (
        f'<main data-class-code="{escape(class_code)}" '
        f'data-session-number="{escape(session_number)}"></main>'
    )
