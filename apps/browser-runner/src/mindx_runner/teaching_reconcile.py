from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .teaching_models import TeachingBatchExtract, TeachingSessionExtract


class TeachingSessionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    internal_id: str = Field(min_length=1, max_length=200)
    verified_internal_id: str | None = Field(default=None, max_length=200)
    class_code: str = Field(min_length=1, max_length=120)
    source_session_id: str | None = Field(default=None, max_length=200)
    session_number: int | None = Field(default=None, ge=1)
    session_type: str | None = Field(default=None, max_length=80)
    scheduled_date: date
    start_time: time
    end_time: time
    source_page_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["active", "quarantined"] = "active"

    @field_validator("internal_id")
    @classmethod
    def normalize_internal_id(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            raise ValueError("internal_id is required")
        return cleaned

    @field_validator("class_code")
    @classmethod
    def normalize_class_code(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            raise ValueError("class_code is required")
        return cleaned.upper()

    @field_validator("verified_internal_id", "source_session_id", "session_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None

    @field_validator("session_type")
    @classmethod
    def normalize_session_type(cls, value: str | None) -> str | None:
        return value.casefold() if value is not None else None

    @model_validator(mode="after")
    def validate_identity_and_time(self) -> "TeachingSessionRecord":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    action: str
    record_id: str | None = None
    reason_code: str | None = None


class _ReconcileQuarantine(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code


class TeachingReconciliationStore:
    def __init__(self, records: Iterable[TeachingSessionRecord] = ()) -> None:
        self._records = list(records)
        internal_ids = [record.internal_id for record in self._records]
        if len(internal_ids) != len(set(internal_ids)):
            raise ValueError("duplicate internal_id")
        source_ids = [
            record.source_session_id
            for record in self._records
            if record.source_session_id is not None
        ]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate source_session_id")
        verified_ids = [
            record.verified_internal_id
            for record in self._records
            if record.verified_internal_id is not None
        ]
        if len(verified_ids) != len(set(verified_ids)):
            raise ValueError("duplicate verified_internal_id")
        self._next_id = 1

    @property
    def records(self) -> tuple[TeachingSessionRecord, ...]:
        return tuple(self._records)

    def reconcile(self, batch: TeachingBatchExtract) -> list[ReconcileResult]:
        if "TEACHING_LOGIN_REQUIRED" in batch.warnings and batch.sessions:
            raise RuntimeError("TEACHING_LOGIN_REQUIRED")
        if not batch.sessions:
            return []

        ambiguous_observations = self._duplicate_observations(batch)
        results: list[ReconcileResult] = []
        for observation in batch.sessions:
            if observation in ambiguous_observations:
                results.append(
                    ReconcileResult(
                        action="quarantined",
                        reason_code="TEACHING_AMBIGUOUS_MATCH",
                    )
                )
                continue
            results.append(self._reconcile_one(observation, batch.source_page_hash))
        return results

    @staticmethod
    def _duplicate_observations(
        batch: TeachingBatchExtract,
    ) -> set[TeachingSessionExtract]:
        counts: dict[tuple[str, ...], int] = {}
        observation_keys: dict[TeachingSessionExtract, set[tuple[str, ...]]] = {}
        for observation in batch.sessions:
            keys: set[tuple[str, ...]] = set()
            if observation.source_session_id is not None:
                keys.add(("source", observation.source_session_id))
            if observation.verified_internal_id is not None:
                keys.add(("verified", observation.verified_internal_id))
            if observation.session_number is not None and observation.session_type is not None:
                keys.add(
                    (
                        "tuple",
                        observation.class_code,
                        str(observation.session_number),
                        observation.session_type,
                    )
                )
            observation_keys[observation] = keys
            for key in keys:
                counts[key] = counts.get(key, 0) + 1
        duplicate_keys = {key for key, count in counts.items() if count > 1}
        return {
            observation
            for observation, keys in observation_keys.items()
            if any(
                key in duplicate_keys
                and (
                    key[0] in {"source", "verified"}
                    or (
                        key[0] == "tuple"
                        and observation.source_session_id is None
                        and observation.verified_internal_id is None
                    )
                )
                for key in keys
            )
        }

    def _reconcile_one(
        self, observation: TeachingSessionExtract, source_page_hash: str
    ) -> ReconcileResult:
        if observation.session_type is None or observation.session_number is None:
            return ReconcileResult(
                action="quarantined",
                reason_code="TEACHING_SESSION_IDENTITY_UNRESOLVABLE",
            )
        try:
            candidates = self._find_candidates(observation)
        except _ReconcileQuarantine as error:
            return ReconcileResult(action="quarantined", reason_code=error.reason_code)
        if len(candidates) > 1:
            return ReconcileResult(
                action="quarantined",
                reason_code="TEACHING_AMBIGUOUS_MATCH",
            )
        if not candidates:
            record = self._new_record(observation, source_page_hash)
            self._records.append(record)
            return ReconcileResult(action="created", record_id=record.internal_id)

        current = candidates[0]
        updated = TeachingSessionRecord(
            internal_id=current.internal_id,
            verified_internal_id=(
                observation.verified_internal_id or current.verified_internal_id
            ),
            class_code=observation.class_code,
            source_session_id=observation.source_session_id or current.source_session_id,
            session_number=observation.session_number,
            session_type=observation.session_type,
            scheduled_date=observation.scheduled_date,
            start_time=observation.start_time,
            end_time=observation.end_time,
            source_page_hash=source_page_hash,
            status="active",
        )
        if updated == current:
            return ReconcileResult(action="unchanged", record_id=current.internal_id)

        index = self._records.index(current)
        self._records[index] = updated
        return ReconcileResult(action="updated", record_id=current.internal_id)

    def _find_candidates(
        self, observation: TeachingSessionExtract
    ) -> list[TeachingSessionRecord]:
        if observation.source_session_id is not None:
            source_matches = [
                record
                for record in self._records
                if record.source_session_id == observation.source_session_id
            ]
            if source_matches:
                if observation.verified_internal_id is not None and not any(
                    record.internal_id == observation.verified_internal_id
                    or record.verified_internal_id == observation.verified_internal_id
                    for record in source_matches
                ):
                    raise _ReconcileQuarantine("TEACHING_INTERNAL_ID_MISMATCH")
                return source_matches

        if observation.verified_internal_id is not None:
            internal_matches = [
                record
                for record in self._records
                if record.internal_id == observation.verified_internal_id
                or record.verified_internal_id == observation.verified_internal_id
            ]
            if internal_matches:
                if observation.source_session_id is not None and any(
                    record.source_session_id not in {None, observation.source_session_id}
                    for record in internal_matches
                ):
                    raise _ReconcileQuarantine("TEACHING_SOURCE_ID_MISMATCH")
                return internal_matches
            raise _ReconcileQuarantine("TEACHING_INTERNAL_ID_UNRESOLVABLE")

        if observation.source_session_id is not None:
            tuple_matches = self._find_tuple_candidates(observation)
            if len(tuple_matches) == 1 and tuple_matches[0].source_session_id is None:
                return tuple_matches
            if tuple_matches:
                reason = (
                    "TEACHING_AMBIGUOUS_MATCH"
                    if len(tuple_matches) > 1
                    else "TEACHING_SOURCE_ID_MISMATCH"
                )
                raise _ReconcileQuarantine(reason)

        if observation.session_number is None or observation.session_type is None:
            return []
        return self._find_tuple_candidates(observation)

    def _find_tuple_candidates(
        self, observation: TeachingSessionExtract
    ) -> list[TeachingSessionRecord]:
        if observation.session_number is None or observation.session_type is None:
            return []
        return [
            record
            for record in self._records
            if record.class_code == observation.class_code
            and record.session_number == observation.session_number
            and record.session_type == observation.session_type
        ]

    def _new_record(
        self, observation: TeachingSessionExtract, source_page_hash: str
    ) -> TeachingSessionRecord:
        existing_ids = {record.internal_id for record in self._records}
        internal_id = f"teaching-session-{self._next_id}"
        while internal_id in existing_ids:
            self._next_id += 1
            internal_id = f"teaching-session-{self._next_id}"
        self._next_id += 1
        return TeachingSessionRecord(
            internal_id=internal_id,
            verified_internal_id=None,
            class_code=observation.class_code,
            source_session_id=observation.source_session_id,
            session_number=observation.session_number,
            session_type=observation.session_type,
            scheduled_date=observation.scheduled_date,
            start_time=observation.start_time,
            end_time=observation.end_time,
            source_page_hash=source_page_hash,
        )
