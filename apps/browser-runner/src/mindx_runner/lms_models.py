import unicodedata
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AttendanceValue = Literal["present", "online", "absent", "unknown"]


def _clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return " ".join(normalized.split()).strip()


class LmsRosterRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    student_id: str | None = Field(default=None, max_length=200)
    discriminator: str | None = Field(default=None, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    attendance: AttendanceValue

    @field_validator("student_id", "discriminator")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_text(value)
        return cleaned or None

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("full_name is required")
        return cleaned


class LmsPageExtract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    class_code: str = Field(min_length=1, max_length=120)
    session_number: int = Field(ge=1)
    scheduled_date: date
    start_time: time
    end_time: time
    source_session_id: str | None = Field(default=None, max_length=200)
    rows: tuple[LmsRosterRow, ...]
    lesson: str = Field(min_length=1, max_length=200)
    homework: str | None = Field(default=None, max_length=500)
    source_page_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    warnings: tuple[str, ...] = ()

    @field_validator("class_code", "lesson")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("required text is missing")
        return cleaned

    @field_validator("source_session_id", "homework")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_text(value)
        return cleaned or None

    @model_validator(mode="after")
    def validate_time_range(self) -> "LmsPageExtract":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self
