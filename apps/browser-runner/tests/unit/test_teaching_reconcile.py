from datetime import date, time

import pytest
from pydantic import ValidationError

from mindx_runner.teaching_models import TeachingBatchExtract, TeachingSessionExtract
from mindx_runner.teaching_reconcile import (
    TeachingReconciliationStore,
    TeachingSessionRecord,
)


def session(
    *,
    class_code: str = "SYN-ROBOTICS-01",
    source_session_id: str | None = "teach-sess-001",
    verified_internal_id: str | None = None,
    session_number: int | None = 3,
    session_type: str | None = "regular",
    scheduled_date: date = date(2026, 8, 17),
    start_time: time = time(9, 0),
    end_time: time = time(10, 30),
) -> TeachingSessionExtract:
    return TeachingSessionExtract(
        class_code=class_code,
        source_session_id=source_session_id,
        verified_internal_id=verified_internal_id,
        session_number=session_number,
        session_type=session_type,
        scheduled_date=scheduled_date,
        start_time=start_time,
        end_time=end_time,
    )


def batch(
    *sessions_to_reconcile: TeachingSessionExtract, hash_value: str = "a" * 64
) -> TeachingBatchExtract:
    return TeachingBatchExtract(
        sessions=list(sessions_to_reconcile), source_page_hash=hash_value
    )


def test_reconcile_creates_a_new_session_from_a_verified_observation() -> None:
    store = TeachingReconciliationStore()

    results = store.reconcile(batch(session()))

    assert results[0].action == "created"
    assert results[0].reason_code is None
    assert results[0].record_id is not None
    assert len(store.records) == 1
    assert store.records[0].source_session_id == "teach-sess-001"


def test_reconcile_is_idempotent_on_a_second_identical_run() -> None:
    store = TeachingReconciliationStore()
    observed = batch(session())

    first = store.reconcile(observed)
    second = store.reconcile(observed)

    assert first[0].action == "created"
    assert second[0].action == "unchanged"
    assert len(store.records) == 1


def test_reconcile_uses_verified_internal_mapping_before_tuple_fallback() -> None:
    record = TeachingSessionRecord(
        internal_id="session-verified",
        verified_internal_id="session-verified",
        class_code="SYN-ROBOTICS-01",
        source_session_id=None,
        session_number=3,
        session_type="regular",
        scheduled_date=date(2026, 8, 17),
        start_time=time(9, 0),
        end_time=time(10, 30),
        source_page_hash="b" * 64,
    )
    store = TeachingReconciliationStore([record])

    result = store.reconcile(
        batch(
            TeachingSessionExtract(
                class_code="SYN-ROBOTICS-01",
                verified_internal_id="session-verified",
                session_number=3,
                session_type="regular",
                scheduled_date=date(2026, 8, 19),
                start_time=time(11, 0),
                end_time=time(12, 30),
            )
        )
    )[0]

    assert result.action == "updated"
    assert result.record_id == "session-verified"
    assert store.records[0].scheduled_date == date(2026, 8, 19)


def test_reconcile_prefers_verified_internal_mapping_when_source_id_is_new() -> None:
    record = TeachingSessionRecord(
        internal_id="session-verified",
        verified_internal_id="session-verified",
        class_code="SYN-ROBOTICS-01",
        source_session_id=None,
        session_number=3,
        session_type="regular",
        scheduled_date=date(2026, 8, 17),
        start_time=time(9, 0),
        end_time=time(10, 30),
        source_page_hash="b" * 64,
    )
    store = TeachingReconciliationStore([record])

    result = store.reconcile(
        batch(
            TeachingSessionExtract(
                class_code="SYN-ROBOTICS-01",
                source_session_id="teach-sess-new",
                verified_internal_id="session-verified",
                session_number=3,
                session_type="regular",
                scheduled_date=date(2026, 8, 19),
                start_time=time(11, 0),
                end_time=time(12, 30),
            )
        )
    )[0]

    assert result.action == "updated"
    assert store.records[0].source_session_id == "teach-sess-new"


def test_reconcile_quarantines_duplicate_source_less_observations_in_one_batch() -> None:
    store = TeachingReconciliationStore()
    observations = batch(
        session(source_session_id=None),
        session(source_session_id=None),
    )

    results = store.reconcile(observations)

    assert [result.action for result in results] == ["quarantined", "quarantined"]
    assert all(result.reason_code == "TEACHING_AMBIGUOUS_MATCH" for result in results)
    assert store.records == ()


def test_reconcile_quarantines_source_less_observation_when_tuple_has_trusted_peer() -> None:
    store = TeachingReconciliationStore()
    observations = batch(
        session(source_session_id="source-a"),
        session(source_session_id=None),
    )

    results = store.reconcile(observations)

    assert [result.action for result in results] == ["created", "quarantined"]
    assert results[1].reason_code == "TEACHING_AMBIGUOUS_MATCH"
    assert len(store.records) == 1


def test_reconcile_quarantines_duplicate_verified_observations_in_one_batch() -> None:
    store = TeachingReconciliationStore()
    observations = batch(
        session(source_session_id=None, verified_internal_id="same-verified-id"),
        session(source_session_id=None, verified_internal_id="same-verified-id"),
    )

    results = store.reconcile(observations)

    assert [result.action for result in results] == ["quarantined", "quarantined"]
    assert all(result.reason_code == "TEACHING_AMBIGUOUS_MATCH" for result in results)
    assert store.records == ()


def test_reconcile_does_not_store_an_unknown_verified_internal_id() -> None:
    store = TeachingReconciliationStore()

    result = store.reconcile(
        batch(session(source_session_id=None, verified_internal_id="untrusted-page-claim"))
    )[0]

    assert result.action == "quarantined"
    assert result.reason_code == "TEACHING_INTERNAL_ID_UNRESOLVABLE"
    assert store.records == ()


def test_reconcile_rejects_duplicate_internal_record_ids() -> None:
    record = TeachingSessionRecord(
        internal_id="duplicate",
        class_code="SYN-ROBOTICS-01",
        source_session_id=None,
        session_number=3,
        session_type="regular",
        scheduled_date=date(2026, 8, 17),
        start_time=time(9, 0),
        end_time=time(10, 30),
        source_page_hash="b" * 64,
    )

    with pytest.raises(ValueError, match="duplicate internal_id"):
        TeachingReconciliationStore([record, record])


def test_reconcile_rejects_duplicate_verified_internal_ids() -> None:
    record = TeachingSessionRecord(
        internal_id="record-a",
        verified_internal_id="same-verified-id",
        class_code="SYN-ROBOTICS-01",
        source_session_id=None,
        session_number=3,
        session_type="regular",
        scheduled_date=date(2026, 8, 17),
        start_time=time(9, 0),
        end_time=time(10, 30),
        source_page_hash="b" * 64,
    )
    duplicate = record.model_copy(update={"internal_id": "record-b"})

    with pytest.raises(ValueError, match="duplicate verified_internal_id"):
        TeachingReconciliationStore([record, duplicate])


def test_session_record_rejects_blank_required_identity_fields() -> None:
    record_values = {
        "internal_id": "valid-internal-id",
        "class_code": "SYN-ROBOTICS-01",
        "session_number": 3,
        "session_type": "regular",
        "scheduled_date": date(2026, 8, 17),
        "start_time": time(9, 0),
        "end_time": time(10, 30),
        "source_page_hash": "b" * 64,
    }

    with pytest.raises(ValidationError):
        TeachingSessionRecord(**{**record_values, "internal_id": "   "})
    with pytest.raises(ValidationError):
        TeachingSessionRecord(**{**record_values, "class_code": "   "})
def test_reconcile_updates_schedule_when_source_identity_is_stable() -> None:
    store = TeachingReconciliationStore()
    store.reconcile(batch(session()))

    result = store.reconcile(
        batch(
            session(
                scheduled_date=date(2026, 8, 19),
                start_time=time(11, 0),
                end_time=time(12, 30),
            )
        )
    )[0]

    assert result.action == "updated"
    assert store.records[0].scheduled_date == date(2026, 8, 19)
    assert store.records[0].start_time == time(11, 0)


def test_reconcile_keeps_makeup_or_repeat_as_a_separate_session_type() -> None:
    store = TeachingReconciliationStore()
    store.reconcile(batch(session()))

    result = store.reconcile(
        batch(
            session(
                source_session_id=None,
                session_type="makeup",
                scheduled_date=date(2026, 8, 20),
            )
        )
    )[0]

    assert result.action == "created"
    assert len(store.records) == 2
    assert {record.session_type for record in store.records} == {"regular", "makeup"}


def test_reconcile_quarantines_missing_session_type() -> None:
    store = TeachingReconciliationStore()

    result = store.reconcile(batch(session(source_session_id=None, session_type=None)))[0]

    assert result.action == "quarantined"
    assert result.reason_code == "TEACHING_SESSION_IDENTITY_UNRESOLVABLE"
    assert store.records == ()


def test_reconcile_quarantines_missing_session_type_even_with_source_id() -> None:
    store = TeachingReconciliationStore()
    store.reconcile(batch(session()))

    result = store.reconcile(
        batch(session(session_type=None))
    )[0]

    assert result.action == "quarantined"
    assert result.reason_code == "TEACHING_SESSION_IDENTITY_UNRESOLVABLE"
    assert store.records[0].session_type == "regular"


def test_reconcile_quarantines_multiple_identity_candidates() -> None:
    seeded = (
        TeachingSessionRecord(
            internal_id="session-a",
            class_code="SYN-ROBOTICS-01",
            source_session_id=None,
            session_number=3,
            session_type="regular",
            scheduled_date=date(2026, 8, 17),
            start_time=time(9, 0),
            end_time=time(10, 30),
            source_page_hash="b" * 64,
        ),
        TeachingSessionRecord(
            internal_id="session-b",
            class_code="SYN-ROBOTICS-01",
            source_session_id=None,
            session_number=3,
            session_type="regular",
            scheduled_date=date(2026, 8, 18),
            start_time=time(9, 0),
            end_time=time(10, 30),
            source_page_hash="c" * 64,
        ),
    )
    store = TeachingReconciliationStore(seeded)

    result = store.reconcile(
        batch(session(source_session_id=None, scheduled_date=date(2026, 8, 19)))
    )[0]

    assert result.action == "quarantined"
    assert result.reason_code == "TEACHING_AMBIGUOUS_MATCH"
    assert len(store.records) == 2


def test_reconcile_quarantines_conflicting_source_identity() -> None:
    store = TeachingReconciliationStore()
    store.reconcile(batch(session(source_session_id="teach-sess-001")))

    result = store.reconcile(
        batch(session(source_session_id="teach-sess-999"))
    )[0]

    assert result.action == "quarantined"
    assert result.reason_code == "TEACHING_SOURCE_ID_MISMATCH"
    assert len(store.records) == 1
    assert store.records[0].source_session_id == "teach-sess-001"


def test_reconcile_attaches_late_source_identity_to_one_unidentified_record() -> None:
    store = TeachingReconciliationStore()
    store.reconcile(batch(session(source_session_id=None)))

    result = store.reconcile(
        batch(session(source_session_id="teach-sess-001"))
    )[0]

    assert result.action == "updated"
    assert store.records[0].source_session_id == "teach-sess-001"
    assert len(store.records) == 1


def test_empty_batch_does_not_mass_cancel_existing_sessions() -> None:
    store = TeachingReconciliationStore()
    store.reconcile(batch(session()))
    empty = TeachingBatchExtract(
        sessions=[], source_page_hash="d" * 64, warnings=["TEACHING_SCHEDULE_EMPTY"]
    )

    assert store.reconcile(empty) == []
    assert len(store.records) == 1
    assert store.records[0].status == "active"


def test_reconcile_rejects_non_empty_batch_with_login_warning() -> None:
    store = TeachingReconciliationStore()
    invalid = TeachingBatchExtract(
        sessions=[session()], source_page_hash="e" * 64, warnings=["TEACHING_LOGIN_REQUIRED"]
    )

    with pytest.raises(RuntimeError, match="TEACHING_LOGIN_REQUIRED"):
        store.reconcile(invalid)
