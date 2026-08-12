from datetime import date, time

import pytest

from mindx_runner.lms_context import (
    ExpectedLmsContext,
    LmsContextAssertion,
    assert_lms_context,
    can_process_lms_roster,
)
from mindx_runner.lms_models import LmsPageExtract, LmsRosterRow


def build_observed_context(
    *,
    class_code: str = "SYN-CLASS-01",
    session_number: int = 3,
    scheduled_date: date = date(2026, 8, 17),
    start_time: time = time(9, 0),
    end_time: time = time(10, 30),
    source_session_id: str | None = "lms-sess-001",
) -> LmsPageExtract:
    return LmsPageExtract(
        class_code=class_code,
        session_number=session_number,
        scheduled_date=scheduled_date,
        start_time=start_time,
        end_time=end_time,
        source_session_id=source_session_id,
        rows=(
            LmsRosterRow(
                student_id="std-001",
                discriminator="disc-001",
                full_name="Nguyễn Ánh",
                attendance="present",
            ),
        ),
        lesson="Dự án Robot cơ bản",
        homework="Hoàn thành bài 1",
        source_page_hash="0" * 64,
        warnings=(),
    )


def build_expected_context(
    *,
    class_code: str = "SYN-CLASS-01",
    session_number: int = 3,
    scheduled_date: date = date(2026, 8, 17),
    start_time: time = time(9, 0),
    end_time: time = time(10, 30),
    source_session_id: str | None = "lms-sess-001",
) -> ExpectedLmsContext:
    return ExpectedLmsContext(
        class_code=class_code,
        session_number=session_number,
        scheduled_date=scheduled_date,
        start_time=start_time,
        end_time=end_time,
        source_session_id=source_session_id,
    )


def test_assert_lms_context_matches_exact_context() -> None:
    result = assert_lms_context(build_expected_context(), build_observed_context())

    assert result == LmsContextAssertion(
        matched=True,
        reason_code="LMS_CONTEXT_MATCH",
        manual_fallback=False,
    )


def test_assert_lms_context_normalizes_class_code_with_trim_and_uppercase_only() -> None:
    result = assert_lms_context(
        build_expected_context(class_code="  syn-class-01  "),
        build_observed_context(class_code="syn-class-01"),
    )

    assert result == LmsContextAssertion(
        matched=True,
        reason_code="LMS_CONTEXT_MATCH",
        manual_fallback=False,
    )


@pytest.mark.parametrize(
    "observed_class_code",
    ["SYN-CLASS-010", "SYN-CLASS-01-EXTRA"],
)
def test_assert_lms_context_rejects_similar_class_codes_without_prefix_matching(
    observed_class_code: str,
) -> None:
    result = assert_lms_context(
        build_expected_context(class_code="SYN-CLASS-01"),
        build_observed_context(class_code=observed_class_code),
    )

    assert result == LmsContextAssertion(
        matched=False,
        reason_code="LMS_CLASS_MISMATCH",
        manual_fallback=True,
    )


@pytest.mark.parametrize(
    ("field_name", "expected_kwargs", "observed_kwargs", "reason_code"),
    [
        (
            "session_number",
            {"session_number": 3},
            {"session_number": 4},
            "LMS_SESSION_MISMATCH",
        ),
        (
            "scheduled_date",
            {"scheduled_date": date(2026, 8, 17)},
            {"scheduled_date": date(2026, 8, 18)},
            "LMS_DATE_MISMATCH",
        ),
        (
            "start_time",
            {"start_time": time(9, 0)},
            {"start_time": time(9, 15)},
            "LMS_TIME_MISMATCH",
        ),
        (
            "end_time",
            {"end_time": time(10, 30)},
            {"end_time": time(11, 0)},
            "LMS_TIME_MISMATCH",
        ),
        (
            "source_session_id",
            {"source_session_id": "lms-sess-001"},
            {"source_session_id": "lms-sess-999"},
            "LMS_SOURCE_ID_MISMATCH",
        ),
    ],
)
def test_assert_lms_context_returns_safe_fallback_on_mismatch(
    field_name: str,
    expected_kwargs: dict[str, object],
    observed_kwargs: dict[str, object],
    reason_code: str,
) -> None:
    del field_name
    expected = build_expected_context(**expected_kwargs)
    observed = build_observed_context(**observed_kwargs)

    result = assert_lms_context(expected, observed)

    assert result == LmsContextAssertion(
        matched=False,
        reason_code=reason_code,
        manual_fallback=True,
    )


def test_assert_lms_context_requires_source_id_to_match_exactly_when_present() -> None:
    result = assert_lms_context(
        build_expected_context(source_session_id=None),
        build_observed_context(source_session_id="lms-sess-001"),
    )

    assert result == LmsContextAssertion(
        matched=False,
        reason_code="LMS_SOURCE_ID_MISMATCH",
        manual_fallback=True,
    )


def test_context_mismatch_blocks_roster_processing_contract() -> None:
    assertion = assert_lms_context(
        build_expected_context(class_code="SYN-CLASS-01"),
        build_observed_context(class_code="SYN-CLASS-010"),
    )
    processed_rows: list[str] = []

    def process_roster() -> None:
        processed_rows.append("processed")

    if can_process_lms_roster(assertion):
        process_roster()

    assert assertion.matched is False
    assert assertion.manual_fallback is True
    assert processed_rows == []
