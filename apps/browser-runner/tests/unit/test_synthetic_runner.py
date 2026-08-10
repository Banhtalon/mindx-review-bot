from pathlib import Path

import pytest

from mindx_runner.synthetic_runner import run_synthetic_fixture

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_synthetic_runner_separates_navigation_from_roster() -> None:
    result = run_synthetic_fixture(
        navigation_html=(FIXTURE_DIR / "lms_navigation.html").read_text(encoding="utf-8"),
        roster_html=(FIXTURE_DIR / "lms_roster.html").read_text(encoding="utf-8"),
        expected_class_code="SYN-CLASS-01",
        expected_session_number=3,
    )

    assert result.class_code == "SYN-CLASS-01"
    assert result.session_number == 3
    assert result.student_ids == ("syn-02", "syn-01")
    assert result.agent_received_roster is False


def test_synthetic_runner_rejects_unexpected_navigation_identity() -> None:
    with pytest.raises(RuntimeError, match="Synthetic navigation identity mismatch"):
        run_synthetic_fixture(
            navigation_html=(FIXTURE_DIR / "lms_navigation.html").read_text(encoding="utf-8"),
            roster_html=(FIXTURE_DIR / "lms_roster.html").read_text(encoding="utf-8"),
            expected_class_code="SYN-CLASS-02",
            expected_session_number=3,
        )


def test_synthetic_runner_rejects_ambiguous_navigation_identity() -> None:
    with pytest.raises(RuntimeError, match="Navigation page identity is unresolvable"):
        run_synthetic_fixture(
            navigation_html=(
                '<main data-class-code="SYN-CLASS-01" data-session-number="3">'
                '<section data-class-code="SYN-CLASS-02"></section>'
                "</main>"
            ),
            roster_html=(FIXTURE_DIR / "lms_roster.html").read_text(encoding="utf-8"),
            expected_class_code="SYN-CLASS-01",
            expected_session_number=3,
        )
