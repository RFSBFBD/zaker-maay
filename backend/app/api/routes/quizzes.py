from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.resources import _accessible_subject
from app.core.auth import get_current_profile
from app.db.models import QuizAttempt, QuizQuestion, Resource, StudyQuiz, UserProfile
from app.db.session import get_db
from app.services.ai_router import safe_call_ai
from app.services.gemini import (
    GeminiNotConfigured,
    GeminiRateLimited,
    GeminiRequestFailed,
    generate_quiz_draft,
)
from app.services.retrieval import sample_for_subject

router = APIRouter(prefix="/api/v1/subjects/{subject_id}/quizzes", tags=["quizzes"])


class QuestionView(BaseModel):
    id: UUID
    prompt: str
    options: list[str]
    source_file: str | None
    source_page: int | None


class QuizView(BaseModel):
    id: UUID
    subject_id: UUID
    title: str
    created_at: datetime
    questions: list[QuestionView]


class QuizSummary(BaseModel):
    id: UUID
    title: str
    question_count: int
    created_at: datetime


class AnswerInput(BaseModel):
    question_id: UUID
    selected_answer: int = Field(ge=0, le=3)


class AttemptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[AnswerInput] = Field(min_length=3, max_length=5)

    @field_validator("answers")
    @classmethod
    def reject_duplicate_questions(cls, answers: list[AnswerInput]) -> list[AnswerInput]:
        ids = [answer.question_id for answer in answers]
        if len(ids) != len(set(ids)):
            raise ValueError("Each quiz question can be answered only once.")
        return answers


class QuestionReview(BaseModel):
    question_id: UUID
    prompt: str
    options: list[str]
    selected_answer: int
    correct_answer: int
    is_correct: bool
    explanation: str
    source_file: str | None
    source_page: int | None


class AttemptResponse(BaseModel):
    id: UUID
    quiz_id: UUID
    score: int
    total_questions: int
    submitted_at: datetime
    review: list[QuestionReview]


class AttemptSummary(BaseModel):
    id: UUID
    score: int
    total_questions: int
    submitted_at: datetime


def _questions(db: Session, quiz_id: UUID) -> list[QuizQuestion]:
    return list(db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.position)).all())


def _quiz_view(db: Session, quiz: StudyQuiz) -> QuizView:
    questions = []
    for question in _questions(db, quiz.id):
        source = db.get(Resource, question.source_resource_id) if question.source_resource_id else None
        questions.append(
            QuestionView(
                id=question.id,
                prompt=question.prompt,
                options=question.options,
                source_file=source.file_name if source else None,
                source_page=question.source_page,
            )
        )
    return QuizView(
        id=quiz.id,
        subject_id=quiz.subject_id,
        title=quiz.title,
        created_at=quiz.created_at,
        questions=questions,
    )


def _attempt_view(db: Session, attempt: QuizAttempt, answers: dict[UUID, int]) -> AttemptResponse:
    review: list[QuestionReview] = []
    for question in _questions(db, attempt.quiz_id):
        source = db.get(Resource, question.source_resource_id) if question.source_resource_id else None
        selected = answers[question.id]
        review.append(
            QuestionReview(
                question_id=question.id,
                prompt=question.prompt,
                options=question.options,
                selected_answer=selected,
                correct_answer=question.correct_answer,
                is_correct=selected == question.correct_answer,
                explanation=question.explanation,
                source_file=source.file_name if source else None,
                source_page=question.source_page,
            )
        )
    return AttemptResponse(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        score=attempt.score,
        total_questions=attempt.total_questions,
        submitted_at=attempt.submitted_at,
        review=review,
    )


@router.get("", response_model=list[QuizSummary])
def list_quizzes(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[QuizSummary]:
    _accessible_subject(db, subject_id, profile)
    quizzes = db.scalars(
        select(StudyQuiz).where(StudyQuiz.subject_id == subject_id).order_by(StudyQuiz.created_at.desc())
    ).all()
    return [
        QuizSummary(
            id=quiz.id,
            title=quiz.title,
            question_count=len(_questions(db, quiz.id)),
            created_at=quiz.created_at,
        )
        for quiz in quizzes
    ]


@router.post("", response_model=QuizView, status_code=status.HTTP_201_CREATED)
def create_quiz(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> QuizView:
    _accessible_subject(db, subject_id, profile)
    passages = sample_for_subject(db, subject_id=subject_id)
    if not passages:
        raise HTTPException(status_code=422, detail="لا توجد مقاطع نصية كافية لإنشاء اختبار.")
    try:
        draft = safe_call_ai(generate_quiz_draft, passages, db=db)
    except GeminiNotConfigured:
        raise HTTPException(status_code=503, detail="إنشاء الاختبارات غير مهيأ حاليًا.") from None
    except GeminiRateLimited:
        raise HTTPException(status_code=429, detail="وصل المساعد إلى حد الطلبات. حاول لاحقًا.") from None
    except GeminiRequestFailed:
        raise HTTPException(status_code=502, detail="تعذر إنشاء الاختبار الآن. حاول مجددًا.") from None

    quiz = StudyQuiz(subject_id=subject_id, created_by=profile.id, title=draft.title)
    db.add(quiz)
    try:
        db.flush()
        questions = []
        for index, question in enumerate(draft.questions):
            source = passages[question.source_index - 1]
            questions.append(
                QuizQuestion(
                    quiz_id=quiz.id,
                    position=index,
                    prompt=question.prompt,
                    options=question.options,
                    correct_answer=question.correct_answer,
                    explanation=question.explanation,
                    source_resource_id=source.resource_id,
                    source_page=source.page_number,
                )
            )
        db.add_all(questions)
        db.commit()
        db.refresh(quiz)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="تعذر حفظ الاختبار.") from None
    return _quiz_view(db, quiz)


@router.get("/{quiz_id}", response_model=QuizView)
def get_quiz(
    subject_id: UUID,
    quiz_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> QuizView:
    _accessible_subject(db, subject_id, profile)
    quiz = db.scalar(select(StudyQuiz).where(StudyQuiz.id == quiz_id, StudyQuiz.subject_id == subject_id))
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    return _quiz_view(db, quiz)


@router.post("/{quiz_id}/attempts", response_model=AttemptResponse, status_code=status.HTTP_201_CREATED)
def submit_attempt(
    subject_id: UUID,
    quiz_id: UUID,
    payload: AttemptInput,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> AttemptResponse:
    _accessible_subject(db, subject_id, profile)
    quiz = db.scalar(select(StudyQuiz).where(StudyQuiz.id == quiz_id, StudyQuiz.subject_id == subject_id))
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    questions = _questions(db, quiz.id)
    answers = {item.question_id: item.selected_answer for item in payload.answers}
    if len(answers) != len(questions) or set(answers) != {question.id for question in questions}:
        raise HTTPException(status_code=422, detail="Submit exactly one answer for every quiz question.")
    score = sum(answers[question.id] == question.correct_answer for question in questions)
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=profile.id,
        score=score,
        total_questions=len(questions),
        answers=[{"question_id": str(question_id), "selected_answer": choice} for question_id, choice in answers.items()],
    )
    db.add(attempt)
    try:
        db.commit()
        db.refresh(attempt)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="تعذر حفظ نتيجة الاختبار.") from None
    return _attempt_view(db, attempt, answers)


@router.get("/{quiz_id}/attempts", response_model=list[AttemptSummary])
def list_my_attempts(
    subject_id: UUID,
    quiz_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[AttemptSummary]:
    _accessible_subject(db, subject_id, profile)
    if db.scalar(select(StudyQuiz.id).where(StudyQuiz.id == quiz_id, StudyQuiz.subject_id == subject_id)) is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == profile.id)
        .order_by(QuizAttempt.submitted_at.desc())
        .limit(limit)
    ).all()
    return [
        AttemptSummary(
            id=attempt.id,
            score=attempt.score,
            total_questions=attempt.total_questions,
            submitted_at=attempt.submitted_at,
        )
        for attempt in attempts
    ]
