from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.core.config import get_settings
from app.db.models import (
    AIModelConfig,
    QuizAttempt,
    Resource,
    StudyArtifact,
    StudyQuiz,
    StudySession,
    Subject,
    UserProfile,
    YouTubeLink,
)
from app.db.session import get_db
from app.services.ai_router import SUPPORTED_TASK_TYPES, resolve_ai_config

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _require_admin(profile: UserProfile) -> None:
    if profile.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privilege required.",
        )


class AnalyticsResponse(BaseModel):
    total_users: int
    active_users_24h: int
    active_users_7d: int
    students_count: int
    admins_count: int
    total_subjects: int
    total_resources: int
    total_storage_bytes: int
    total_study_sessions: int
    total_quizzes: int
    total_quiz_attempts: int
    average_quiz_score: float
    total_study_artifacts: int
    total_youtube_links: int
    task_models: dict[str, str]


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    display_name: str | None
    role: str
    created_at: datetime
    last_active_at: datetime | None
    subjects_count: int
    quizzes_count: int
    sessions_count: int


class RoleUpdatePayload(BaseModel):
    role: str = Field(pattern=r"^(student|admin)$")


class AIConfigItem(BaseModel):
    task_type: str
    task_label: str
    model_name: str
    has_custom_api_key: bool
    temperature: float
    max_output_tokens: int
    is_active: bool
    description: str | None
    updated_at: datetime | None


class AIConfigWritePayload(BaseModel):
    task_type: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=2000, ge=64, le=65536)
    is_active: bool = True
    description: str | None = Field(default=None, max_length=255)


class AIConfigTestPayload(BaseModel):
    model_name: str = Field(min_length=1, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)


class AIConfigTestResponse(BaseModel):
    ok: bool
    model: str
    message: str


@router.get("/analytics", response_model=AnalyticsResponse)
def get_platform_analytics(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalyticsResponse:
    _require_admin(profile)
    now = datetime.now(timezone.utc)
    t24h = now - timedelta(hours=24)
    t7d = now - timedelta(days=7)

    total_users = db.scalar(select(func.count(UserProfile.id))) or 0
    active_24h = db.scalar(select(func.count(UserProfile.id)).where(UserProfile.last_active_at >= t24h)) or 0
    active_7d = db.scalar(select(func.count(UserProfile.id)).where(UserProfile.last_active_at >= t7d)) or 0
    students_count = db.scalar(select(func.count(UserProfile.id)).where(UserProfile.role == "student")) or 0
    admins_count = db.scalar(select(func.count(UserProfile.id)).where(UserProfile.role == "admin")) or 0

    total_subjects = db.scalar(select(func.count(Subject.id)).where(Subject.archived_at.is_(None))) or 0
    total_resources = db.scalar(select(func.count(Resource.id))) or 0
    total_storage_bytes = db.scalar(select(func.coalesce(func.sum(Resource.size_bytes), 0))) or 0
    total_study_sessions = db.scalar(select(func.count(StudySession.id))) or 0
    total_quizzes = db.scalar(select(func.count(StudyQuiz.id))) or 0
    total_quiz_attempts = db.scalar(select(func.count(QuizAttempt.id))) or 0

    avg_score_raw = db.scalar(
        select(
            func.avg(
                cast(QuizAttempt.score, Float) / func.nullif(QuizAttempt.total_questions, 0) * 100
            )
        )
    )
    average_quiz_score = round(float(avg_score_raw), 1) if avg_score_raw is not None else 0.0

    total_study_artifacts = db.scalar(select(func.count(StudyArtifact.id))) or 0
    total_youtube_links = db.scalar(select(func.count(YouTubeLink.id))) or 0

    task_models = {
        task: resolve_ai_config(task, db=db).model_name
        for task in SUPPORTED_TASK_TYPES
    }

    return AnalyticsResponse(
        total_users=total_users,
        active_users_24h=active_24h,
        active_users_7d=active_7d,
        students_count=students_count,
        admins_count=admins_count,
        total_subjects=total_subjects,
        total_resources=total_resources,
        total_storage_bytes=total_storage_bytes,
        total_study_sessions=total_study_sessions,
        total_quizzes=total_quizzes,
        total_quiz_attempts=total_quiz_attempts,
        average_quiz_score=average_quiz_score,
        total_study_artifacts=total_study_artifacts,
        total_youtube_links=total_youtube_links,
        task_models=task_models,
    )


@router.get("/users", response_model=list[UserListItem])
def list_users(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserListItem]:
    _require_admin(profile)
    users = db.scalars(select(UserProfile).order_by(UserProfile.created_at.desc())).all()
    items = []
    for user in users:
        subj_count = db.scalar(select(func.count(Subject.id)).where(Subject.created_by == user.id, Subject.archived_at.is_(None))) or 0
        quiz_count = db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id == user.id)) or 0
        sess_count = db.scalar(select(func.count(StudySession.id)).where(StudySession.user_id == user.id)) or 0
        items.append(
            UserListItem(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=user.role,
                created_at=user.created_at,
                last_active_at=user.last_active_at,
                subjects_count=subj_count,
                quizzes_count=quiz_count,
                sessions_count=sess_count,
            )
        )
    return items


@router.patch("/users/{user_id}/role", response_model=UserListItem)
def update_user_role(
    user_id: UUID,
    payload: RoleUpdatePayload,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> UserListItem:
    _require_admin(profile)
    user = db.get(UserProfile, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.id == profile.id and payload.role != "admin":
        # Prevent self-demotion if you are the logged in admin
        admin_count = db.scalar(select(func.count(UserProfile.id)).where(UserProfile.role == "admin")) or 0
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="لا يمكن إلغاء صلاحية آخر مسؤول في النظام.")

    user.role = payload.role
    db.commit()
    db.refresh(user)

    subj_count = db.scalar(select(func.count(Subject.id)).where(Subject.created_by == user.id, Subject.archived_at.is_(None))) or 0
    quiz_count = db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id == user.id)) or 0
    sess_count = db.scalar(select(func.count(StudySession.id)).where(StudySession.user_id == user.id)) or 0

    return UserListItem(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        created_at=user.created_at,
        last_active_at=user.last_active_at,
        subjects_count=subj_count,
        quizzes_count=quiz_count,
        sessions_count=sess_count,
    )


@router.get("/ai-configs", response_model=list[AIConfigItem])
def get_ai_configs(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AIConfigItem]:
    _require_admin(profile)
    existing_records = {
        cfg.task_type: cfg
        for cfg in db.scalars(select(AIModelConfig)).all()
    }

    results = []
    for task_type, label in SUPPORTED_TASK_TYPES.items():
        rec = existing_records.get(task_type)
        resolved = resolve_ai_config(task_type, db=db)
        results.append(
            AIConfigItem(
                task_type=task_type,
                task_label=label,
                model_name=rec.model_name if rec else resolved.model_name,
                has_custom_api_key=bool(rec and rec.api_key),
                temperature=rec.temperature if rec else resolved.temperature,
                max_output_tokens=rec.max_output_tokens if rec else resolved.max_output_tokens,
                is_active=rec.is_active if rec else True,
                description=rec.description if rec else label,
                updated_at=rec.updated_at if rec else None,
            )
        )
    return results


@router.post("/ai-configs", response_model=AIConfigItem)
@router.put("/ai-configs/{task_type}", response_model=AIConfigItem)
def upsert_ai_config(
    payload: AIConfigWritePayload,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    task_type: str | None = None,
) -> AIConfigItem:
    _require_admin(profile)
    target_task_type = task_type or payload.task_type
    config = db.scalar(select(AIModelConfig).where(AIModelConfig.task_type == target_task_type))
    if config is None:
        config = AIModelConfig(
            task_type=target_task_type,
            model_name=payload.model_name.strip(),
            api_key=payload.api_key.strip() if payload.api_key else None,
            temperature=payload.temperature,
            max_output_tokens=payload.max_output_tokens,
            is_active=payload.is_active,
            description=payload.description.strip() if payload.description else None,
        )
        db.add(config)
    else:
        config.model_name = payload.model_name.strip()
        if payload.api_key is not None:
            config.api_key = payload.api_key.strip() if payload.api_key.strip() else None
        config.temperature = payload.temperature
        config.max_output_tokens = payload.max_output_tokens
        config.is_active = payload.is_active
        if payload.description is not None:
            config.description = payload.description.strip()

    db.commit()
    db.refresh(config)

    return AIConfigItem(
        task_type=config.task_type,
        task_label=SUPPORTED_TASK_TYPES.get(config.task_type, config.task_type),
        model_name=config.model_name,
        has_custom_api_key=bool(config.api_key),
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        is_active=config.is_active,
        description=config.description,
        updated_at=config.updated_at,
    )


@router.post("/ai-configs/test", response_model=AIConfigTestResponse)
def test_ai_model(
    payload: AIConfigTestPayload,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
) -> AIConfigTestResponse:
    _require_admin(profile)
    settings = get_settings()
    api_key = payload.api_key or settings.gemini_api_key
    if not api_key:
        return AIConfigTestResponse(
            ok=False,
            model=payload.model_name,
            message="لم يتم توفير مفتاح API صالح للاختبار.",
        )

    client = None
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=10_000),
        )
        response = client.models.generate_content(
            model=payload.model_name,
            contents="Say 'OK'",
            config=types.GenerateContentConfig(
                max_output_tokens=16,
                thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            ),
        )
        if response.text and response.text.strip():
            return AIConfigTestResponse(
                ok=True,
                model=payload.model_name,
                message=f"النموذج متصل ويعمل بنجاح: {response.text.strip()[:30]}",
            )
        return AIConfigTestResponse(
            ok=False,
            model=payload.model_name,
            message="النموذج استجاب ولكن بدون نص.",
        )
    except Exception as exc:
        return AIConfigTestResponse(
            ok=False,
            model=payload.model_name,
            message=f"تعذر الاتصال بالنموذج: {type(exc).__name__}",
        )
    finally:
        if client is not None:
            client.close()
