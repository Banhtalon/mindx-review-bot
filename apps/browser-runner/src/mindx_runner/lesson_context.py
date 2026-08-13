from collections.abc import Sequence
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .lesson_context_models import LmsClassExtract, LmsCurriculumEntry, LmsScheduleEntry
from .teaching_models import TeachingSessionExtract

LessonContextStatus = Literal[
    "matched",
    "curriculum_missing",
    "manual_fallback",
    "no_next_session",
]
LessonContextReasonCode = Literal[
    "LESSON_CONTEXT_MATCH",
    "TEACHING_SESSION_NUMBER_MISSING",
    "LMS_CLASS_MISMATCH",
    "LMS_SESSION_NOT_FOUND",
    "LMS_SESSION_AMBIGUOUS",
    "LMS_SCHEDULE_MISMATCH",
    "CURRICULUM_MISSING",
    "CURRICULUM_AMBIGUOUS",
    "NEXT_SESSION_AMBIGUOUS",
    "NO_NEXT_SESSION",
]


class ResolvedLessonContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    class_code: str = Field(min_length=1, max_length=120)
    course_code: str = Field(min_length=1, max_length=120)
    session_number: int = Field(ge=1)
    scheduled_date: date
    start_time: time
    end_time: time
    lesson_title: str = Field(min_length=1, max_length=200)
    homework_title: str | None = Field(default=None, max_length=500)
    block: str | None = Field(default=None, max_length=120)
    special_event: str | None = Field(default=None, max_length=120)


class NextSessionPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    class_code: str = Field(min_length=1, max_length=120)
    session_number: int | None = Field(default=None, ge=1)
    scheduled_date: date
    start_time: time
    end_time: time
    block: str | None = Field(default=None, max_length=120)
    special_event: str | None = Field(default=None, max_length=120)


class LessonContextResolution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: LessonContextStatus
    reason_code: LessonContextReasonCode
    current: ResolvedLessonContext | None = None
    next_session: NextSessionPreview | None = None


def _normalize_class_code(value: str) -> str:
    return " ".join(value.split()).strip().upper()


def _schedule_key(entry: LmsScheduleEntry) -> tuple[date, time, time]:
    return entry.scheduled_date, entry.start_time, entry.end_time


def _teaching_schedule_key(
    session: TeachingSessionExtract,
) -> tuple[date, time, time]:
    return session.scheduled_date, session.start_time, session.end_time


def _manual_fallback(reason_code: LessonContextReasonCode) -> LessonContextResolution:
    return LessonContextResolution(
        status="manual_fallback",
        reason_code=reason_code,
        current=None,
        next_session=None,
    )


def _curriculum_entry(
    curriculum: Sequence[LmsCurriculumEntry],
    session_number: int,
) -> LmsCurriculumEntry | None | Literal["ambiguous"]:
    matches = [entry for entry in curriculum if entry.session_number == session_number]
    if len(matches) > 1:
        return "ambiguous"
    return matches[0] if matches else None


def _next_session(
    current: TeachingSessionExtract,
    teaching_schedule: Sequence[TeachingSessionExtract],
) -> TeachingSessionExtract | None | Literal["ambiguous"]:
    current_key = _teaching_schedule_key(current)
    candidates = [
        session
        for session in teaching_schedule
        if _normalize_class_code(session.class_code) == _normalize_class_code(current.class_code)
        and _teaching_schedule_key(session) > current_key
    ]
    candidates.sort(
        key=lambda session: (
            session.scheduled_date,
            session.start_time,
            session.end_time,
            session.session_number or 0,
        )
    )
    if not candidates:
        return None

    earliest_key = _teaching_schedule_key(candidates[0])
    earliest = [
        session for session in candidates if _teaching_schedule_key(session) == earliest_key
    ]
    if len(earliest) > 1:
        return "ambiguous"
    return candidates[0]


def _to_next_session_preview(session: TeachingSessionExtract) -> NextSessionPreview:
    return NextSessionPreview(
        class_code=_normalize_class_code(session.class_code),
        session_number=session.session_number,
        scheduled_date=session.scheduled_date,
        start_time=session.start_time,
        end_time=session.end_time,
        block=session.block,
        special_event=session.special_event,
    )


def resolve_lesson_context(
    teaching_session: TeachingSessionExtract,
    teaching_schedule: Sequence[TeachingSessionExtract],
    lms_class: LmsClassExtract,
) -> LessonContextResolution:
    session_number = teaching_session.session_number
    if session_number is None:
        return _manual_fallback("TEACHING_SESSION_NUMBER_MISSING")

    if _normalize_class_code(teaching_session.class_code) != _normalize_class_code(
        lms_class.class_code
    ):
        return _manual_fallback("LMS_CLASS_MISMATCH")

    schedule_matches = [
        entry
        for entry in lms_class.scheduled_sessions
        if entry.session_number == session_number
    ]
    if not schedule_matches:
        return _manual_fallback("LMS_SESSION_NOT_FOUND")
    if len(schedule_matches) > 1:
        return _manual_fallback("LMS_SESSION_AMBIGUOUS")

    lms_schedule = schedule_matches[0]
    if _schedule_key(lms_schedule) != _teaching_schedule_key(teaching_session):
        return _manual_fallback("LMS_SCHEDULE_MISMATCH")

    curriculum_entry = _curriculum_entry(lms_class.curriculum, session_number)
    if curriculum_entry == "ambiguous":
        return _manual_fallback("CURRICULUM_AMBIGUOUS")
    if curriculum_entry is None or not curriculum_entry.lesson_title.strip():
        return LessonContextResolution(
            status="curriculum_missing",
            reason_code="CURRICULUM_MISSING",
            current=None,
            next_session=None,
        )

    next_session = _next_session(teaching_session, teaching_schedule)
    if next_session == "ambiguous":
        return _manual_fallback("NEXT_SESSION_AMBIGUOUS")

    current = ResolvedLessonContext(
        class_code=_normalize_class_code(teaching_session.class_code),
        course_code=lms_class.course_code,
        session_number=session_number,
        scheduled_date=teaching_session.scheduled_date,
        start_time=teaching_session.start_time,
        end_time=teaching_session.end_time,
        lesson_title=curriculum_entry.lesson_title,
        homework_title=curriculum_entry.homework_title,
        block=teaching_session.block,
        special_event=teaching_session.special_event,
    )

    if next_session is None:
        return LessonContextResolution(
            status="no_next_session",
            reason_code="NO_NEXT_SESSION",
            current=current,
            next_session=None,
        )

    return LessonContextResolution(
        status="matched",
        reason_code="LESSON_CONTEXT_MATCH",
        current=current,
        next_session=_to_next_session_preview(next_session),
    )
