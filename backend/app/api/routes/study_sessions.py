from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.db.models import StudySession, UserProfile
from app.db.session import get_db
from app.services.study_sessions import (
    ActiveSessionConflict,
    SubjectAccessDenied,
    end_study_session,
    get_active_study_session,
    start_study_session,
)

router = APIRouter(prefix="/api/v1/study-sessions", tags=["study sessions"])


class SessionStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: UUID
    duration_minutes: int = Field(ge=5, le=240)


class SessionResponse(BaseModel):
    id: UUID
    subject_id: UUID
    started_at: datetime
    planned_end_at: datetime
    ended_at: datetime | None
    status: str
    remaining_seconds: int


def to_response(session: StudySession) -> SessionResponse:
    end = session.planned_end_at
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    remaining = max(0, int((end - datetime.now(timezone.utc)).total_seconds()))
    return SessionResponse(
        id=session.id,
        subject_id=session.subject_id,
        started_at=session.started_at,
        planned_end_at=session.planned_end_at,
        ended_at=session.ended_at,
        status=session.status,
        remaining_seconds=remaining if session.status == "active" else 0,
    )


def _require_student(profile: UserProfile) -> None:
    if profile.role not in ("student", "admin"):
        raise HTTPException(status_code=403, detail="Student access required.")


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def start_session(
    payload: SessionStartRequest,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionResponse:
    _require_student(profile)
    try:
        session = start_study_session(
            db,
            user_id=profile.id,
            subject_id=payload.subject_id,
            duration_minutes=payload.duration_minutes,
        )
    except SubjectAccessDenied:
        raise HTTPException(status_code=404, detail="Subject not found.") from None
    except ActiveSessionConflict:
        raise HTTPException(status_code=409, detail="An active study session already exists.") from None
    return to_response(session)


@router.get("/active", response_model=SessionResponse | None)
def active_session(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionResponse | None:
    _require_student(profile)
    session = get_active_study_session(db, user_id=profile.id)
    return to_response(session) if session is not None else None


@router.post("/{session_id}/end", response_model=SessionResponse)
def finish_session(
    session_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionResponse:
    _require_student(profile)
    session = end_study_session(db, session_id=session_id, user_id=profile.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Study session not found.")
    return to_response(session)
