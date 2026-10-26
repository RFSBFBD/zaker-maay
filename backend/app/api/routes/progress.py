from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.db.models import (
    QuizAttempt,
    Resource,
    StudyQuiz,
    StudySession,
    Subject,
    SubjectMembership,
    UserProfile,
)
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


class SubjectProgress(BaseModel):
    subject_id: UUID
    subject_name: str
    study_seconds: int
    quiz_attempts: int
    quiz_average_percent: float | None
    last_studied_at: datetime | None


class ProgressResponse(BaseModel):
    study_seconds: int
    quiz_attempts: int
    quiz_average_percent: float | None
    subjects: list[SubjectProgress]


@router.get("/me", response_model=ProgressResponse)
def my_progress(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> ProgressResponse:
    subject_query = select(Subject).where(Subject.archived_at.is_(None)).order_by(Subject.name)
    if profile.role != "admin":
        subject_query = subject_query.join(SubjectMembership).where(SubjectMembership.user_id == profile.id)
    subjects = list(db.scalars(subject_query).all())
    now = datetime.now(timezone.utc)
    breakdown: list[SubjectProgress] = []
    all_scored = 0
    all_questions = 0

    for subject in subjects:
        sessions = db.scalars(
            select(StudySession).where(
                StudySession.user_id == profile.id,
                StudySession.subject_id == subject.id,
            )
        ).all()
        study_seconds = 0
        last_studied: datetime | None = None
        for session in sessions:
            start = session.started_at
            end = session.ended_at or (session.planned_end_at if session.status != "active" else now)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            planned_end = session.planned_end_at
            if planned_end.tzinfo is None:
                planned_end = planned_end.replace(tzinfo=timezone.utc)
            end = min(end, planned_end, now)
            study_seconds += max(0, int((end - start).total_seconds()))
            occurred_at = session.ended_at or session.started_at
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
            if occurred_at and (last_studied is None or occurred_at > last_studied):
                last_studied = occurred_at

        attempts = db.execute(
            select(QuizAttempt.score, QuizAttempt.total_questions)
            .join(StudyQuiz, StudyQuiz.id == QuizAttempt.quiz_id)
            .where(StudyQuiz.subject_id == subject.id, QuizAttempt.user_id == profile.id)
        ).all()
        scored = sum(row.score for row in attempts)
        total = sum(row.total_questions for row in attempts)
        all_scored += scored
        all_questions += total
        breakdown.append(
            SubjectProgress(
                subject_id=subject.id,
                subject_name=subject.name,
                study_seconds=study_seconds,
                quiz_attempts=len(attempts),
                quiz_average_percent=round(scored * 100 / total, 1) if total else None,
                last_studied_at=last_studied,
            )
        )

    attempts_count = sum(item.quiz_attempts for item in breakdown)
    return ProgressResponse(
        study_seconds=sum(item.study_seconds for item in breakdown),
        quiz_attempts=attempts_count,
        quiz_average_percent=round(all_scored * 100 / all_questions, 1)
        if all_questions
        else None,
        subjects=breakdown,
    )


def _skill_level_description(level: int) -> str:
    """Return an Arabic description for a skill level (1-10)."""
    if level <= 3:
        return "مبتدئ"
    if level <= 6:
        return "متوسط"
    return "متقدم"


class DashboardResponse(BaseModel):
    skill_level: int
    level_description: str
    total_subjects: int
    total_resources: int
    total_study_seconds: int
    quiz_average: float | None
    total_quizzes_taken: int


@router.get("/me/dashboard", response_model=DashboardResponse)
def my_dashboard(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> DashboardResponse:
    """Return a high-level student dashboard summary."""
    # ── Subjects enrolled ────────────────────────────────────────────
    subject_query = select(Subject.id).where(Subject.archived_at.is_(None))
    if profile.role != "admin":
        subject_query = subject_query.join(SubjectMembership).where(SubjectMembership.user_id == profile.id)
    subject_ids = list(db.scalars(subject_query).all())
    total_subjects = len(subject_ids)

    # ── Resources across those subjects ──────────────────────────────
    total_resources = 0
    if subject_ids:
        total_resources = db.scalar(
            select(func.count(Resource.id)).where(Resource.subject_id.in_(subject_ids))
        ) or 0

    # ── Total study time ─────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    sessions = db.scalars(
        select(StudySession).where(StudySession.user_id == profile.id)
    ).all()
    total_study_seconds = 0
    for session in sessions:
        start = session.started_at
        end = session.ended_at or (session.planned_end_at if session.status != "active" else now)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        planned_end = session.planned_end_at
        if planned_end.tzinfo is None:
            planned_end = planned_end.replace(tzinfo=timezone.utc)
        end = min(end, planned_end, now)
        total_study_seconds += max(0, int((end - start).total_seconds()))

    # ── Quiz stats ───────────────────────────────────────────────────
    attempts = db.execute(
        select(QuizAttempt.score, QuizAttempt.total_questions).where(
            QuizAttempt.user_id == profile.id
        )
    ).all()
    total_quizzes_taken = len(attempts)
    scored = sum(row.score for row in attempts)
    total_questions = sum(row.total_questions for row in attempts)
    quiz_average = round(scored * 100 / total_questions, 1) if total_questions else None

    skill = profile.skill_level or 1
    return DashboardResponse(
        skill_level=skill,
        level_description=_skill_level_description(skill),
        total_subjects=total_subjects,
        total_resources=total_resources,
        total_study_seconds=total_study_seconds,
        quiz_average=quiz_average,
        total_quizzes_taken=total_quizzes_taken,
    )
