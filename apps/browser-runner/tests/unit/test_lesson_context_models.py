from datetime import date, time

import pytest
from pydantic import ValidationError

from mindx_runner.lesson_context_models import (
    LmsClassExtract,
    LmsCurriculumEntry,
    LmsScheduleEntry,
)


def schedule_entry(
    *,
    session_number: int = 3,
    scheduled_date: date = date(2026, 8, 17),
    start_time: time = time(9, 0),
    end_time: time = time(10, 30),
) -> LmsScheduleEntry:
    return LmsScheduleEntry(
        session_number=session_number,
        scheduled_date=scheduled_date,
        start_time=start_time,
        end_time=end_time,
    )


def curriculum_entry(
    *,
    session_number: int = 3,
    lesson_title: str = "Synthetic current lesson",
    homework_title: str | None = "Synthetic homework",
) -> LmsCurriculumEntry:
    return LmsCurriculumEntry(
        session_number=session_number,
        lesson_title=lesson_title,
        homework_title=homework_title,
    )


def lms_class(
    *,
    scheduled_sessions: tuple[LmsScheduleEntry, ...] = (schedule_entry(),),
    curriculum: tuple[LmsCurriculumEntry, ...] = (curriculum_entry(),),
    total_sessions: int = 14,
) -> LmsClassExtract:
    return LmsClassExtract(
        class_code=" syn-js-02 ",
        course_code=" jsb ",
        course_name=" Web Developer Basic ",
        total_sessions=total_sessions,
        scheduled_sessions=scheduled_sessions,
        curriculum=curriculum,
        operation_mode=" offline ",
    )


def test_models_normalize_class_and_course_text() -> None:
    result = lms_class()

    assert result.class_code == "SYN-JS-02"
    assert result.course_code == "JSB"
    assert result.course_name == "Web Developer Basic"
    assert result.operation_mode == "OFFLINE"
    assert result.curriculum[0].homework_title == "Synthetic homework"


def test_schedule_rejects_an_end_time_before_start_time() -> None:
    with pytest.raises(ValidationError):
        schedule_entry(start_time=time(11, 0), end_time=time(10, 30))


def test_class_rejects_duplicate_schedule_session_numbers() -> None:
    with pytest.raises(ValidationError):
        lms_class(
            scheduled_sessions=(
                schedule_entry(session_number=3),
                schedule_entry(session_number=3, scheduled_date=date(2026, 8, 24)),
            )
        )


def test_class_rejects_duplicate_curriculum_session_numbers() -> None:
    with pytest.raises(ValidationError):
        lms_class(
            curriculum=(
                curriculum_entry(session_number=3),
                curriculum_entry(session_number=3, lesson_title="Duplicate"),
            )
        )


def test_curriculum_rejects_a_blank_lesson_title() -> None:
    with pytest.raises(ValidationError):
        curriculum_entry(lesson_title="  ")


def test_class_rejects_a_schedule_session_beyond_total_sessions() -> None:
    with pytest.raises(ValidationError):
        lms_class(
            total_sessions=3,
            scheduled_sessions=(schedule_entry(session_number=4),),
        )
