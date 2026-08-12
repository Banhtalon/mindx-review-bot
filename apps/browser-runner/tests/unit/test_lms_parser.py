from datetime import date, time
from pathlib import Path

import pytest

from mindx_runner.lms_models import LmsPageExtract, LmsRosterRow
from mindx_runner.lms_parser import (
    DEFAULT_SYNTHETIC_CLASS_CODES,
    LmsParserError,
    parse_lms_page,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "lms"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parser_extracts_normal_session_with_normalized_safe_fields() -> None:
    page = parse_lms_page(read_fixture("normal-session.html"))

    assert page == LmsPageExtract(
        class_code="SYN-CLASS-01",
        session_number=3,
        scheduled_date=date(2026, 8, 17),
        start_time=time(9, 0),
        end_time=time(10, 30),
        source_session_id="lms-sess-001",
        lesson="Dự án Robot cơ bản",
        homework="Hoàn thành bài 1",
        rows=(
            LmsRosterRow(
                student_id="std-001",
                discriminator="disc-001",
                full_name="Nguyễn Ánh",
                attendance="present",
            ),
            LmsRosterRow(
                student_id="std-002",
                discriminator="disc-002",
                full_name="Trần Bình",
                attendance="online",
            ),
            LmsRosterRow(
                student_id="std-003",
                discriminator="disc-003",
                full_name="Lê Cường",
                attendance="absent",
            ),
            LmsRosterRow(
                student_id="std-004",
                discriminator="disc-004",
                full_name="Phạm Dung",
                attendance="unknown",
            ),
        ),
        source_page_hash=page.source_page_hash,
        warnings=(),
    )
    assert len(page.source_page_hash) == 64
    assert page.source_page_hash == parse_lms_page(
        read_fixture("normal-session.html")
    ).source_page_hash


def test_parser_treats_blank_homework_as_none() -> None:
    page = parse_lms_page(read_fixture("no-homework.html"))

    assert page.lesson == "Bài tổng kết"
    assert page.homework is None


def test_parser_preserves_duplicate_display_names_when_identifiers_are_unique() -> None:
    page = parse_lms_page(read_fixture("duplicate-name.html"))

    assert [row.full_name for row in page.rows] == ["Nguyễn Hà", "Nguyễn Hà"]
    assert [row.student_id for row in page.rows] == ["std-010", "std-011"]


def test_parser_allows_duplicate_display_names_without_identifiers_when_rows_are_ambiguous(
) -> None:
    page = parse_lms_page(read_fixture("ambiguous-name.html"))

    assert page.rows == (
        LmsRosterRow(
            student_id=None,
            discriminator=None,
            full_name="Nguyễn Hà",
            attendance="present",
        ),
        LmsRosterRow(
            student_id=None,
            discriminator=None,
            full_name="Nguyễn Hà",
            attendance="online",
        ),
    )


def test_parser_rejects_similar_but_not_exact_class_codes() -> None:
    with pytest.raises(LmsParserError, match="LMS_UNKNOWN_CLASS_CODE"):
        parse_lms_page(read_fixture("similar-class.html"))


def test_parser_uses_exact_explicit_allowlist_without_prefix_matching() -> None:
    html = read_fixture("normal-session.html")

    parsed = parse_lms_page(html, allowed_class_codes={"SYN-CLASS-01"})
    assert parsed.class_code == "SYN-CLASS-01"

    with pytest.raises(LmsParserError, match="LMS_UNKNOWN_CLASS_CODE"):
        parse_lms_page(html, allowed_class_codes={"SYN-CLASS"})


def test_parser_is_row_order_invariant_for_semantic_identity() -> None:
    first = parse_lms_page(read_fixture("normal-session.html"))
    reordered = parse_lms_page(read_fixture("row-reordered.html"))

    assert first.class_code == reordered.class_code
    assert first.session_number == reordered.session_number
    assert first.source_session_id == reordered.source_session_id
    assert {row.student_id for row in first.rows} == {row.student_id for row in reordered.rows}
    assert {row.discriminator for row in first.rows} == {
        row.discriminator for row in reordered.rows
    }
    assert {(row.student_id, row.full_name, row.attendance) for row in first.rows} == {
        (row.student_id, row.full_name, row.attendance) for row in reordered.rows
    }


def test_parser_rejects_duplicate_non_null_student_ids() -> None:
    duplicate_html = read_fixture("normal-session.html").replace(
        'data-student-id="std-004"', 'data-student-id=" std-001 "', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DUPLICATE_STUDENT_ID"):
        parse_lms_page(duplicate_html)


def test_parser_rejects_duplicate_non_null_discriminators() -> None:
    duplicate_html = read_fixture("normal-session.html").replace(
        'data-discriminator="disc-004"', 'data-discriminator=" disc-001 "', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DUPLICATE_DISCRIMINATOR"):
        parse_lms_page(duplicate_html)


def test_parser_rejects_blank_required_context_fields() -> None:
    invalid_html = read_fixture("normal-session.html").replace(
        'data-class-code=" SYN-CLASS-01 "', 'data-class-code="   "', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DATA_INVALID"):
        parse_lms_page(invalid_html)


def test_parser_rejects_invalid_attendance_values_with_safe_code() -> None:
    invalid_html = read_fixture("normal-session.html").replace(
        'data-attendance="present"', 'data-attendance="late"', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DATA_INVALID"):
        parse_lms_page(invalid_html)


def test_parser_rejects_blank_but_present_student_id() -> None:
    invalid_html = read_fixture("normal-session.html").replace(
        'data-student-id=" std-001 "', 'data-student-id="   "', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DATA_INVALID"):
        parse_lms_page(invalid_html)


def test_parser_rejects_blank_but_present_discriminator() -> None:
    invalid_html = read_fixture("normal-session.html").replace(
        'data-discriminator=" disc-001 "', 'data-discriminator="   "', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DATA_INVALID"):
        parse_lms_page(invalid_html)


def test_parser_ignores_decoy_rows_outside_the_active_context_block() -> None:
    page = parse_lms_page(read_fixture("outside-context-decoy.html"))

    assert page.rows == (
        LmsRosterRow(
            student_id="std-030",
            discriminator="disc-030",
            full_name="Student Inside",
            attendance="online",
        ),
    )


def test_parser_rejects_invalid_session_number_with_safe_code() -> None:
    invalid_html = read_fixture("normal-session.html").replace(
        'data-session-number="3"', 'data-session-number="not-a-number"', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DATA_INVALID"):
        parse_lms_page(invalid_html)


def test_parser_rejects_invalid_scheduled_date_with_safe_code() -> None:
    invalid_html = read_fixture("normal-session.html").replace(
        'data-scheduled-date="2026-08-17"', 'data-scheduled-date="2026-99-17"', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DATA_INVALID"):
        parse_lms_page(invalid_html)


def test_parser_rejects_invalid_time_values_with_safe_code() -> None:
    invalid_html = read_fixture("normal-session.html").replace(
        'data-start-time="09:00"', 'data-start-time="25:61"', 1
    )

    with pytest.raises(LmsParserError, match="LMS_DATA_INVALID"):
        parse_lms_page(invalid_html)


def test_default_allowlist_is_the_single_synthetic_class_from_the_brief() -> None:
    assert DEFAULT_SYNTHETIC_CLASS_CODES == frozenset({"SYN-CLASS-01"})
