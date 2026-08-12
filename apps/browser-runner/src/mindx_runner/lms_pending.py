from datetime import date, datetime, time, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PendingSessionInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    class_code: str
    session_number: int
    scheduled_date: date
    start_time: time
    end_time: time
    workflow_status: Literal["context_pending", "completed", "failed", "skipped"]


class PendingSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    eligible: bool
    reason_code: str


def _has_complete_identity(session: PendingSessionInput) -> bool:
    return bool(session.class_code.strip()) and session.session_number >= 1


def select_pending_session(
    session: PendingSessionInput, *, now: datetime
) -> PendingSelection:
    if not _has_complete_identity(session):
        return PendingSelection(eligible=False, reason_code="PENDING_IDENTITY_INCOMPLETE")

    if session.workflow_status != "context_pending":
        return PendingSelection(eligible=False, reason_code="PENDING_WORKFLOW_NOT_PENDING")

    yesterday = now.date() - timedelta(days=1)
    today = now.date()
    end_at = datetime.combine(session.scheduled_date, session.end_time)

    if session.scheduled_date < yesterday:
        return PendingSelection(eligible=False, reason_code="PENDING_TOO_OLD")
    if session.scheduled_date > today:
        return PendingSelection(eligible=False, reason_code="PENDING_FUTURE")
    if end_at > now:
        return PendingSelection(eligible=False, reason_code="PENDING_FUTURE")

    return PendingSelection(eligible=True, reason_code="PENDING_ELIGIBLE")
