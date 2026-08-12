from datetime import date, time
from pathlib import Path

import pytest

from mindx_runner.teaching_parser import TeachingParserError, parse_teaching_schedule

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "teaching"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parser_extracts_normal_week_into_validated_records() -> None:
    batch = parse_teaching_schedule(read_fixture("normal-week.html"))

    assert len(batch.sessions) == 2
    assert batch.sessions[0].class_code == "SYN-ROBOTICS-01"
    assert batch.sessions[0].source_session_id == "teach-sess-001"
    assert batch.sessions[0].session_number == 3
    assert batch.sessions[0].session_type == "regular"
    assert batch.sessions[0].scheduled_date == date(2026, 8, 17)
    assert batch.sessions[0].start_time == time(9, 0)
    assert batch.sessions[0].end_time == time(10, 30)
    assert batch.sessions[0].teacher_name == "Synthetic Teacher"
    assert len(batch.source_page_hash) == 64
    assert batch.warnings == []


def test_parser_reports_a_real_empty_week_without_error() -> None:
    batch = parse_teaching_schedule(read_fixture("empty-week.html"))

    assert batch.sessions == []
    assert batch.warnings == ["TEACHING_SCHEDULE_EMPTY"]


def test_parser_rejects_login_page_instead_of_treating_it_as_empty() -> None:
    with pytest.raises(TeachingParserError, match="TEACHING_LOGIN_REQUIRED"):
        parse_teaching_schedule(read_fixture("login-page.html"))


def test_parser_uses_semantic_attributes_when_generated_css_classes_change() -> None:
    batch = parse_teaching_schedule(read_fixture("css-class-change.html"))

    assert [(session.class_code, session.source_session_id) for session in batch.sessions] == [
        ("SYN-ROBOTICS-01", "teach-sess-001")
    ]


def test_parser_rejects_invalid_schedule_values_with_safe_code() -> None:
    invalid_html = read_fixture("normal-week.html").replace(
        'data-start-time="09:00"', 'data-start-time="not-a-time"', 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(invalid_html)


def test_parser_rejects_duplicate_source_session_ids() -> None:
    duplicate_html = read_fixture("normal-week.html").replace(
        'data-source-session-id="teach-sess-002"',
        'data-source-session-id="teach-sess-001"',
        1,
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DUPLICATE_SOURCE_ID"):
        parse_teaching_schedule(duplicate_html)


def test_parser_rejects_source_ids_that_only_differ_by_whitespace() -> None:
    duplicate_html = read_fixture("normal-week.html").replace(
        'data-source-session-id="teach-sess-002"',
        'data-source-session-id=" teach-sess-001 "',
        1,
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DUPLICATE_SOURCE_ID"):
        parse_teaching_schedule(duplicate_html)


def test_parser_rejects_a_session_that_ends_before_it_starts() -> None:
    invalid_html = read_fixture("normal-week.html").replace(
        'data-end-time="10:30"', 'data-end-time="08:30"', 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(invalid_html)


def test_parser_hash_is_stable_for_the_same_page_bytes() -> None:
    html = read_fixture("normal-week.html")

    assert parse_teaching_schedule(html).source_page_hash == parse_teaching_schedule(
        html
    ).source_page_hash
