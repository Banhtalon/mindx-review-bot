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


def run_synthetic_fixture(
    *,
    navigation_html: str,
    roster_html: str,
    expected_class_code: str,
    expected_session_number: int,
) -> SyntheticRunResult:
    agent_page = assert_agent_page_safe(navigation_html)
    class_matches = re.findall(r'data-class-code="([^"]+)"', agent_page)
    session_matches = re.findall(r'data-session-number="([0-9]+)"', agent_page)
    if len(class_matches) != 1 or len(session_matches) != 1:
        raise RuntimeError("Synthetic navigation identity is unresolvable")

    class_code = class_matches[0]
    session_number = int(session_matches[0])
    if (
        class_code != expected_class_code
        or session_number != expected_session_number
    ):
        raise RuntimeError("Synthetic navigation identity mismatch")

    rows = parse_student_rows(roster_html)
    student_ids = tuple(row.student_id for row in rows)
    if any(student_id is None for student_id in student_ids):
        raise RuntimeError("Synthetic roster is missing stable identifiers")

    return SyntheticRunResult(
        class_code=class_code,
        session_number=session_number,
        student_ids=tuple(student_id for student_id in student_ids if student_id is not None),
        agent_received_roster=False,
    )
