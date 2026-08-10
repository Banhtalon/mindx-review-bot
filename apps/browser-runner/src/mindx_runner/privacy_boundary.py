import re

ROSTER_MARKER = re.compile(
    r"data-student-id|data-discriminator|data-roster|id=[\"']roster[\"']",
    re.IGNORECASE,
)


def assert_agent_page_safe(page_html: str) -> str:
    if ROSTER_MARKER.search(page_html):
        raise RuntimeError("Navigation agent cannot receive roster page")
    return page_html
