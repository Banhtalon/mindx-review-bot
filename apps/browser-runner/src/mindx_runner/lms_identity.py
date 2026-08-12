import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .lms_models import LmsRosterRow

StudentResolutionStatus = Literal["resolved", "unresolvable", "ambiguous"]


def _clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return " ".join(normalized.split()).strip()


def _name_key(value: str) -> str:
    return _clean_text(value).casefold()


def _has_stable_identity(row: LmsRosterRow) -> bool:
    return row.student_id is not None or row.discriminator is not None


class ExpectedStudent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    internal_id: str = Field(min_length=1, max_length=200)
    student_id: str | None = Field(default=None, max_length=200)
    discriminator: str | None = Field(default=None, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)

    @field_validator("internal_id")
    @classmethod
    def normalize_internal_id(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("internal_id is required")
        return cleaned

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


class StudentResolution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    internal_id: str | None = Field(default=None, max_length=200)
    status: StudentResolutionStatus
    reason_code: str = Field(min_length=1, max_length=200)


def _resolved(internal_id: str, reason_code: str) -> StudentResolution:
    return StudentResolution(
        internal_id=internal_id,
        status="resolved",
        reason_code=reason_code,
    )


def _unresolvable() -> StudentResolution:
    return StudentResolution(
        internal_id=None,
        status="unresolvable",
        reason_code="LMS_STUDENT_IDENTITY_UNRESOLVABLE",
    )


def _ambiguous() -> StudentResolution:
    return StudentResolution(
        internal_id=None,
        status="ambiguous",
        reason_code="LMS_STUDENT_IDENTITY_AMBIGUOUS",
    )


def _has_duplicate_non_null(values: tuple[str | None, ...]) -> bool:
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        if value in seen:
            return True
        seen.add(value)
    return False


def resolve_lms_student(
    expected: ExpectedStudent, rows: tuple[LmsRosterRow, ...]
) -> StudentResolution:
    if _has_duplicate_non_null(tuple(row.student_id for row in rows)):
        return _ambiguous()
    if _has_duplicate_non_null(tuple(row.discriminator for row in rows)):
        return _ambiguous()

    if expected.student_id is not None:
        for row in rows:
            if row.student_id == expected.student_id:
                return _resolved(expected.internal_id, "LMS_STUDENT_ID_MATCH")
        if expected.discriminator is None:
            return _unresolvable()

    if expected.discriminator is not None:
        for row in rows:
            if row.discriminator == expected.discriminator:
                return _resolved(expected.internal_id, "LMS_STUDENT_DISCRIMINATOR_MATCH")
        return _unresolvable()

    candidates = [row for row in rows if _name_key(row.full_name) == _name_key(expected.full_name)]
    stable_candidates = [row for row in candidates if _has_stable_identity(row)]

    if len(stable_candidates) == 1:
        return _resolved(expected.internal_id, "LMS_STUDENT_NAME_MATCH")
    if len(candidates) > 1 and stable_candidates:
        return _ambiguous()
    return _unresolvable()
