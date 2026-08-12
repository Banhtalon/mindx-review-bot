from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, time

from .teaching_models import TeachingBatchExtract, TeachingSessionExtract


@dataclass(frozen=True, slots=True)
class TeachingSessionRecord:
    internal_id: str
    class_code: str
    source_session_id: str | None
    session_number: int | None
    session_type: str | None
    scheduled_date: date
    start_time: time
    end_time: time
    source_page_hash: str
    status: str = "active"


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
        self._next_id = len(self._records) + 1

    @property
    def records(self) -> tuple[TeachingSessionRecord, ...]:
        return tuple(self._records)

    def reconcile(self, batch: TeachingBatchExtract) -> list[ReconcileResult]:
        if "TEACHING_LOGIN_REQUIRED" in batch.warnings and batch.sessions:
            raise RuntimeError("TEACHING_LOGIN_REQUIRED")
        if not batch.sessions:
            return []

        results: list[ReconcileResult] = []
        for observation in batch.sessions:
            results.append(self._reconcile_one(observation, batch.source_page_hash))
        return results

    def _reconcile_one(
        self, observation: TeachingSessionExtract, source_page_hash: str
    ) -> ReconcileResult:
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
            if observation.session_type is None or observation.session_number is None:
                return ReconcileResult(
                    action="quarantined",
                    reason_code="TEACHING_SESSION_IDENTITY_UNRESOLVABLE",
                )
            record = self._new_record(observation, source_page_hash)
            self._records.append(record)
            return ReconcileResult(action="created", record_id=record.internal_id)

        current = candidates[0]
        updated = replace(
            current,
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
                return source_matches

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
        internal_id = f"teaching-session-{self._next_id}"
        self._next_id += 1
        return TeachingSessionRecord(
            internal_id=internal_id,
            class_code=observation.class_code,
            source_session_id=observation.source_session_id,
            session_number=observation.session_number,
            session_type=observation.session_type,
            scheduled_date=observation.scheduled_date,
            start_time=observation.start_time,
            end_time=observation.end_time,
            source_page_hash=source_page_hash,
        )
