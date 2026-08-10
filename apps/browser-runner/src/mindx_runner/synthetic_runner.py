import re
from dataclasses import dataclass

from .parser import parse_student_rows
from .privacy_boundary import assert_agent_page_safe


@dataclass(frozen=True)
class SyntheticRunResult:
    class_code: str
    session_number: int
    student_ids: tuple[str, ...]
    agent_received_roster: bool


def run_synthetic_fixture(*, navigation_html: str, roster_html: str) -> SyntheticRunResult:
    agent_page = assert_agent_page_safe(navigation_html)
    class_match = re.search(r'data-class-code="([^"]+)"', agent_page)
    session_match = re.search(r'data-session-number="([0-9]+)"', agent_page)
    if class_match is None or session_match is None:
        raise RuntimeError("Synthetic navigation fixture is incomplete")

    rows = parse_student_rows(roster_html)
    student_ids = tuple(row.student_id for row in rows)
    if any(student_id is None for student_id in student_ids):
        raise RuntimeError("Synthetic roster is missing stable identifiers")

    return SyntheticRunResult(
        class_code=class_match.group(1),
        session_number=int(session_match.group(1)),
        student_ids=tuple(student_id for student_id in student_ids if student_id is not None),
        agent_received_roster=False,
    )
