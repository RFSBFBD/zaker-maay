from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import StudySession, Subject, SubjectMembership


class SubjectAccessDenied(Exception):
    pass


class ActiveSessionConflict(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def start_study_session(
    db: Session,
    *,
    user_id: UUID,
    subject_id: UUID,
    duration_minutes: int,
    now: datetime | None = None,
) -> StudySession:
    server_now = ensure_utc(now or utc_now())
    is_member = db.scalar(
        select(SubjectMembership.user_id)
        .join(Subject, Subject.id == SubjectMembership.subject_id)
        .where(
            SubjectMembership.user_id == user_id,
            SubjectMembership.subject_id == subject_id,
            Subject.archived_at.is_(None),
        )
    )
    if is_member is None:
        raise SubjectAccessDenied

    active = db.scalar(
        select(StudySession).where(
            StudySession.user_id == user_id,
            StudySession.status == "active",
        )
    )
    if active is not None:
        if ensure_utc(active.planned_end_at) > server_now:
            raise ActiveSessionConflict
        active.status = "completed"
        active.ended_at = active.planned_end_at
        db.flush()

    session = StudySession(
        user_id=user_id,
        subject_id=subject_id,
        started_at=server_now,
        planned_end_at=server_now + timedelta(minutes=duration_minutes),
        status="active",
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ActiveSessionConflict from None
    db.refresh(session)
    return session


def get_active_study_session(
    db: Session, *, user_id: UUID, now: datetime | None = None
) -> StudySession | None:
    server_now = ensure_utc(now or utc_now())
    session = db.scalar(
        select(StudySession).where(
            StudySession.user_id == user_id,
            StudySession.status == "active",
        )
    )
    if session is not None and ensure_utc(session.planned_end_at) <= server_now:
        session.status = "completed"
        session.ended_at = session.planned_end_at
        db.commit()
        return None
    return session


def end_study_session(
    db: Session,
    *,
    session_id: UUID,
    user_id: UUID,
    now: datetime | None = None,
) -> StudySession | None:
    server_now = ensure_utc(now or utc_now())
    session = db.scalar(
        select(StudySession).where(
            StudySession.id == session_id,
            StudySession.user_id == user_id,
        )
    )
    if session is None:
        return None
    if session.status == "active":
        session.ended_at = min(server_now, ensure_utc(session.planned_end_at))
        session.status = "completed"
        db.commit()
        db.refresh(session)
    return session
