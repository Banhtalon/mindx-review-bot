from datetime import date, datetime, time

from mindx_runner.lms_pending import (
    PendingSelection,
    PendingSessionInput,
    select_pending_session,
)


def pending_session(
    *,
    class_code: str = "SYN-CLASS-01",
    session_number: int = 3,
    scheduled_date: date = date(2026, 8, 12),
    start_time: time = time(9, 0),
    end_time: time = time(10, 30),
    workflow_status: str = "context_pending",
) -> PendingSessionInput:
    return PendingSessionInput(
        class_code=class_code,
        session_number=session_number,
        scheduled_date=scheduled_date,
        start_time=start_time,
        end_time=end_time,
        workflow_status=workflow_status,
    )


def test_selects_eligible_session_ending_today() -> None:
    result = select_pending_session(
        session=pending_session(),
        now=datetime(2026, 8, 12, 11, 0),
    )

    assert result == PendingSelection(eligible=True, reason_code="PENDING_ELIGIBLE")


def test_selects_late_session_from_yesterday() -> None:
    result = select_pending_session(
        session=pending_session(scheduled_date=date(2026, 8, 11), end_time=time(23, 0)),
        now=datetime(2026, 8, 12, 9, 0),
    )

    assert result == PendingSelection(eligible=True, reason_code="PENDING_ELIGIBLE")


def test_rejects_future_session() -> None:
    result = select_pending_session(
        session=pending_session(scheduled_date=date(2026, 8, 13)),
        now=datetime(2026, 8, 12, 9, 0),
    )

    assert result == PendingSelection(eligible=False, reason_code="PENDING_FUTURE")


def test_rejects_session_older_than_yesterday() -> None:
    result = select_pending_session(
        session=pending_session(scheduled_date=date(2026, 8, 10)),
        now=datetime(2026, 8, 12, 9, 0),
    )

    assert result == PendingSelection(eligible=False, reason_code="PENDING_TOO_OLD")


def test_rejects_non_pending_workflow_state() -> None:
    result = select_pending_session(
        session=pending_session(workflow_status="completed"),
        now=datetime(2026, 8, 12, 9, 0),
    )

    assert result == PendingSelection(
        eligible=False,
        reason_code="PENDING_WORKFLOW_NOT_PENDING",
    )


def test_rejects_incomplete_identity() -> None:
    result = select_pending_session(
        session=pending_session(class_code="   "),
        now=datetime(2026, 8, 12, 9, 0),
    )

    assert result == PendingSelection(
        eligible=False,
        reason_code="PENDING_IDENTITY_INCOMPLETE",
    )
