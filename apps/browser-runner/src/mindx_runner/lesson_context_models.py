import unicodedata
from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return " ".join(normalized.split()).strip()


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _clean_text(value)
    return cleaned or None


class LmsScheduleEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_number: int = Field(ge=1)
    scheduled_date: date
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "LmsScheduleEntry":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class LmsCurriculumEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_number: int = Field(ge=1)
    lesson_title: str = Field(min_length=1, max_length=200)
    homework_title: str | None = Field(default=None, max_length=500)

    @field_validator("lesson_title")
    @classmethod
    def normalize_lesson_title(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("lesson_title is required")
        return cleaned

    @field_validator("homework_title")
    @classmethod
    def normalize_homework_title(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class LmsClassExtract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    class_code: str = Field(min_length=1, max_length=120)
    course_code: str = Field(min_length=1, max_length=120)
    course_name: str = Field(min_length=1, max_length=200)
    total_sessions: int = Field(ge=1)
    scheduled_sessions: tuple[LmsScheduleEntry, ...]
    curriculum: tuple[LmsCurriculumEntry, ...]
    operation_mode: str | None = Field(default=None, max_length=80)

    @field_validator("class_code", "course_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("code is required")
        return cleaned.upper()

    @field_validator("course_name")
    @classmethod
    def normalize_course_name(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("course_name is required")
        return cleaned

    @field_validator("operation_mode")
    @classmethod
    def normalize_operation_mode(cls, value: str | None) -> str | None:
        cleaned = _clean_optional_text(value)
        return cleaned.upper() if cleaned is not None else None

    @model_validator(mode="after")
    def validate_session_keys(self) -> "LmsClassExtract":
        schedule_numbers = [entry.session_number for entry in self.scheduled_sessions]
        if len(schedule_numbers) != len(set(schedule_numbers)):
            raise ValueError("scheduled session numbers must be unique")
        if any(number > self.total_sessions for number in schedule_numbers):
            raise ValueError("scheduled session number exceeds total_sessions")

        curriculum_numbers = [entry.session_number for entry in self.curriculum]
        if len(curriculum_numbers) != len(set(curriculum_numbers)):
            raise ValueError("curriculum session numbers must be unique")
        if any(number > self.total_sessions for number in curriculum_numbers):
            raise ValueError("curriculum session number exceeds total_sessions")
        return self
