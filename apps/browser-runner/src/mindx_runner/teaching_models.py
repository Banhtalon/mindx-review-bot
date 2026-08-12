from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


class TeachingSessionExtract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    class_code: str = Field(min_length=1, max_length=120)
    source_session_id: str | None = Field(default=None, max_length=200)
    verified_internal_id: str | None = Field(default=None, max_length=200)
    session_number: int | None = Field(default=None, ge=1)
    session_type: str | None = Field(default=None, max_length=80)
    scheduled_date: date
    start_time: time
    end_time: time
    teacher_name: str | None = Field(default=None, max_length=200)

    @field_validator("class_code")
    @classmethod
    def normalize_class_code(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("class_code is required")
        return cleaned.upper()

    @field_validator("source_session_id", "verified_internal_id", "session_type", "teacher_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_text(value)
        return cleaned or None

    @field_validator("session_type")
    @classmethod
    def normalize_session_type(cls, value: str | None) -> str | None:
        return value.casefold() if value is not None else None

    @model_validator(mode="after")
    def validate_time_range(self) -> "TeachingSessionExtract":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class TeachingBatchExtract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sessions: list[TeachingSessionExtract]
    source_page_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    warnings: list[str] = Field(default_factory=list)
