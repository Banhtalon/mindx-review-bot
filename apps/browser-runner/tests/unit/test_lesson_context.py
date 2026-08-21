from datetime import date, time

from mindx_runner.lesson_context import resolve_lesson_context
from mindx_runner.lesson_context_models import (
    LmsClassExtract,
    LmsCurriculumEntry,
    LmsScheduleEntry,
)
from mindx_runner.teaching_models import TeachingSessionExtract


def teaching_session(
    *,
    class_code: str = "SYN-JS-02",
    session_number: int | None = 3,
    scheduled_date: date = date(2026, 8, 17),
    start_time: time = time(9, 0),
    end_time: time = time(10, 30),
    block: str | None = "Coding",
    special_event: str | None = None,
) -> TeachingSessionExtract:
    return TeachingSessionExtract(
        class_code=class_code,
        source_session_id=f"teach-{session_number or 'unknown'}",
        session_number=session_number,
        session_type="regular",
        scheduled_date=scheduled_date,
        start_time=start_time,
        end_time=end_time,
        block=block,
        special_event=special_event,
    )


def lms_schedule(
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


def curriculum(
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
    class_code: str = "SYN-JS-02",
    scheduled_sessions: tuple[LmsScheduleEntry, ...] = (lms_schedule(),),
    curriculum_entries: tuple[LmsCurriculumEntry, ...] = (curriculum(),),
) -> LmsClassExtract:
    return LmsClassExtract(
        class_code=class_code,
        course_code="JSB",
        course_name="Synthetic Web Course",
        total_sessions=14,
        scheduled_sessions=scheduled_sessions,
        curriculum=curriculum_entries,
        operation_mode="OFFLINE",
    )


def test_resolver_returns_current_lesson_and_actual_next_event() -> None:
    current = teaching_session()
    next_event = teaching_session(
        session_number=8,
        scheduled_date=date(2026, 8, 24),
        special_event="SYN-EVENT-01",
    )
    later_event = teaching_session(
        session_number=5,
        scheduled_date=date(2026, 8, 31),
    )

    result = resolve_lesson_context(
        current,
        (later_event, current, next_event),
        lms_class(
            scheduled_sessions=(lms_schedule(),),
            curriculum_entries=(curriculum(),),
        ),
    )

    assert result.status == "matched"
    assert result.reason_code == "LESSON_CONTEXT_MATCH"
    assert result.current is not None
    assert result.current.lesson_title == "Synthetic current lesson"
    assert result.current.homework_title == "Synthetic homework"
    assert result.next_session is not None
    assert result.next_session.session_number == 8
    assert result.next_session.special_event == "SYN-EVENT-01"


def test_resolver_rejects_a_similar_class_code() -> None:
    result = resolve_lesson_context(
        teaching_session(class_code="SYN-JS-020"),
        (teaching_session(class_code="SYN-JS-020"),),
        lms_class(class_code="SYN-JS-02"),
    )

    assert result.status == "manual_fallback"
    assert result.reason_code == "LMS_CLASS_MISMATCH"
    assert result.current is None


def test_resolver_rejects_a_missing_lms_session() -> None:
    result = resolve_lesson_context(
        teaching_session(session_number=4),
        (teaching_session(session_number=4),),
        lms_class(),
    )

    assert result.status == "manual_fallback"
    assert result.reason_code == "LMS_SESSION_NOT_FOUND"


def test_resolver_rejects_a_lms_schedule_date_or_time_mismatch() -> None:
    result = resolve_lesson_context(
        teaching_session(),
        (teaching_session(),),
        lms_class(scheduled_sessions=(lms_schedule(scheduled_date=date(2026, 8, 18)),)),
    )

    assert result.status == "manual_fallback"
    assert result.reason_code == "LMS_SCHEDULE_MISMATCH"


def test_resolver_returns_curriculum_missing_without_fabricating_a_title() -> None:
    result = resolve_lesson_context(
        teaching_session(),
        (teaching_session(),),
        lms_class(curriculum_entries=()),
    )

    assert result.status == "curriculum_missing"
    assert result.reason_code == "CURRICULUM_MISSING"
    assert result.current is None


def test_curriculum_lookup_uses_session_number_not_collection_order() -> None:
    future = teaching_session(session_number=8, scheduled_date=date(2026, 8, 24))

    result = resolve_lesson_context(
        teaching_session(),
        (teaching_session(), future),
        lms_class(
            curriculum_entries=(
                curriculum(session_number=5, lesson_title="Later lesson"),
                curriculum(session_number=3, lesson_title="Current lesson"),
            )
        ),
    )

    assert result.status == "matched"
    assert result.current is not None
    assert result.current.lesson_title == "Current lesson"


def test_resolver_requires_a_teaching_session_number() -> None:
    current = teaching_session(session_number=None)

    result = resolve_lesson_context(current, (current,), lms_class())

    assert result.status == "manual_fallback"
    assert result.reason_code == "TEACHING_SESSION_NUMBER_MISSING"


def test_resolver_rejects_ambiguous_lms_session_boundary_data() -> None:
    current = teaching_session()
    corrupted = LmsClassExtract.model_construct(
        class_code="SYN-JS-02",
        course_code="JSB",
        course_name="Synthetic Web Course",
        total_sessions=14,
        scheduled_sessions=(lms_schedule(), lms_schedule()),
        curriculum=(curriculum(),),
        operation_mode="OFFLINE",
    )

    result = resolve_lesson_context(current, (current,), corrupted)

    assert result.status == "manual_fallback"
    assert result.reason_code == "LMS_SESSION_AMBIGUOUS"


def test_resolver_rejects_ambiguous_earliest_next_event() -> None:
    current = teaching_session()
    first = teaching_session(session_number=4, scheduled_date=date(2026, 8, 24))
    duplicate_time = teaching_session(session_number=5, scheduled_date=date(2026, 8, 24))

    result = resolve_lesson_context(
        current,
        (current, first, duplicate_time),
        lms_class(),
    )

    assert result.status == "manual_fallback"
    assert result.reason_code == "NEXT_SESSION_AMBIGUOUS"
    assert result.current is None


def test_resolver_treats_same_start_time_as_ambiguous_even_with_different_end_times() -> None:
    current = teaching_session()
    first = teaching_session(
        session_number=4,
        scheduled_date=date(2026, 8, 24),
        end_time=time(10, 30),
    )
    overlapping = teaching_session(
        session_number=5,
        scheduled_date=date(2026, 8, 24),
        end_time=time(11, 0),
    )

    result = resolve_lesson_context(
        current,
        (current, first, overlapping),
        lms_class(),
    )

    assert result.status == "manual_fallback"
    assert result.reason_code == "NEXT_SESSION_AMBIGUOUS"
    assert result.current is None


def test_resolver_retains_current_lesson_when_no_next_event_exists() -> None:
    current = teaching_session()

    result = resolve_lesson_context(current, (current,), lms_class())

    assert result.status == "no_next_session"
    assert result.reason_code == "NO_NEXT_SESSION"
    assert result.current is not None
    assert result.next_session is None
