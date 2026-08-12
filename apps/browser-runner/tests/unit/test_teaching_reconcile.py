from datetime import date, time

import pytest

from mindx_runner.teaching_models import TeachingBatchExtract, TeachingSessionExtract
from mindx_runner.teaching_reconcile import (
    TeachingReconciliationStore,
    TeachingSessionRecord,
)


def session(
    *,
    class_code: str = "SYN-ROBOTICS-01",
    source_session_id: str | None = "teach-sess-001",
    session_number: int | None = 3,
    session_type: str | None = "regular",
    scheduled_date: date = date(2026, 8, 17),
    start_time: time = time(9, 0),
    end_time: time = time(10, 30),
) -> TeachingSessionExtract:
    return TeachingSessionExtract(
        class_code=class_code,
        source_session_id=source_session_id,
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
