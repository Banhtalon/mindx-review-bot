from pathlib import Path

from mindx_runner.synthetic_runner import run_synthetic_fixture

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_synthetic_runner_separates_navigation_from_roster() -> None:
    result = run_synthetic_fixture(
        navigation_html=(FIXTURE_DIR / "lms_navigation.html").read_text(encoding="utf-8"),
        roster_html=(FIXTURE_DIR / "lms_roster.html").read_text(encoding="utf-8"),
    )

    assert result.class_code == "SYN-CLASS-01"
    assert result.session_number == 3
    assert result.student_ids == ("syn-02", "syn-01")
    assert result.agent_received_roster is False
