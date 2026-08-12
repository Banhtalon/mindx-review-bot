from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .lms_models import LmsPageExtract


class ExpectedLmsContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    class_code: str = Field(min_length=1, max_length=120)
    session_number: int = Field(ge=1)
    scheduled_date: date
    start_time: time
    end_time: time
    source_session_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_time_range(self) -> "ExpectedLmsContext":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class LmsContextAssertion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    matched: bool
    reason_code: str = Field(min_length=1, max_length=80)
    manual_fallback: bool


def _normalize_class_code(value: str) -> str:
    return value.strip().upper()


def assert_lms_context(
    expected: ExpectedLmsContext,
    observed: LmsPageExtract,
) -> LmsContextAssertion:
    expected_class_code = _normalize_class_code(expected.class_code)
    observed_class_code = _normalize_class_code(observed.class_code)
    if expected_class_code != observed_class_code:
        return LmsContextAssertion(
            matched=False,
            reason_code="LMS_CLASS_MISMATCH",
            manual_fallback=True,
        )

    if expected.session_number != observed.session_number:
        return LmsContextAssertion(
            matched=False,
            reason_code="LMS_SESSION_MISMATCH",
            manual_fallback=True,
        )

    if expected.scheduled_date != observed.scheduled_date:
        return LmsContextAssertion(
            matched=False,
            reason_code="LMS_DATE_MISMATCH",
            manual_fallback=True,
        )

    if expected.start_time != observed.start_time or expected.end_time != observed.end_time:
        return LmsContextAssertion(
            matched=False,
            reason_code="LMS_TIME_MISMATCH",
            manual_fallback=True,
        )

    if expected.source_session_id != observed.source_session_id:
        return LmsContextAssertion(
            matched=False,
            reason_code="LMS_SOURCE_ID_MISMATCH",
            manual_fallback=True,
        )

    return LmsContextAssertion(
        matched=True,
        reason_code="LMS_CONTEXT_MATCH",
        manual_fallback=False,
    )
