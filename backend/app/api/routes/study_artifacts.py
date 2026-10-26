import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.resources import _accessible_subject
from app.core.auth import get_current_profile
from app.core.config import get_settings
from app.db.models import StudyArtifact, UserProfile
from app.db.session import get_db
from app.services.ai_router import safe_call_ai
from app.services.gemini import (
    GeminiNotConfigured,
    GeminiRateLimited,
    GeminiRequestFailed,
    generate_concept_map_draft,
    generate_flashcard_draft,
    generate_study_notes_draft,
)
from app.services.retrieval import RetrievedPassage, sample_for_subject

router = APIRouter(prefix="/api/v1/subjects/{subject_id}/study-artifacts", tags=["study tools"])


class StudyArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["flashcards", "concept_map", "study_notes"]


class StudyArtifactResponse(BaseModel):
    id: UUID
    subject_id: UUID
    kind: str
    title: str
    content: dict[str, Any]
    sources: list[dict[str, Any]]
    model: str
    created_at: datetime
    cached: bool = False


def _cache_key(kind: str, model: str, passages: list[RetrievedPassage]) -> str:
    canonical = {
        "kind": kind,
        "model": model,
        "prompt_version": "study-artifacts-v1",
        "passages": [
            {
                "resource_id": str(passage.resource_id),
                "page_number": passage.page_number,
                "chunk_index": passage.chunk_index,
                "content": passage.content,
            }
            for passage in passages
        ],
    }
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _to_response(artifact: StudyArtifact, *, cached: bool = False) -> StudyArtifactResponse:
    return StudyArtifactResponse(
        id=artifact.id,
        subject_id=artifact.subject_id,
        kind=artifact.kind,
        title=artifact.title,
        content=artifact.content,
        sources=artifact.sources,
        model=artifact.model,
        created_at=artifact.created_at,
        cached=cached,
    )


@router.get("", response_model=list[StudyArtifactResponse])
def list_study_artifacts(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[Literal["flashcards", "concept_map", "study_notes"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[StudyArtifactResponse]:
    _accessible_subject(db, subject_id, profile)
    query = select(StudyArtifact).where(StudyArtifact.subject_id == subject_id)
    if kind:
        query = query.where(StudyArtifact.kind == kind)
    artifacts = db.scalars(query.order_by(StudyArtifact.created_at.desc()).limit(limit)).all()
    return [_to_response(artifact) for artifact in artifacts]


@router.post("", response_model=StudyArtifactResponse, status_code=status.HTTP_201_CREATED)
def create_study_artifact(
    subject_id: UUID,
    payload: StudyArtifactCreate,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> StudyArtifactResponse:
    _accessible_subject(db, subject_id, profile)
    passages = sample_for_subject(db, subject_id=subject_id, limit=6)
    if not passages:
        raise HTTPException(status_code=422, detail="لا توجد مقاطع نصية كافية لإنشاء أداة دراسية.")

    settings = get_settings()
    digest = _cache_key(payload.kind, settings.gemini_model, passages)
    cached_artifact = db.scalar(
        select(StudyArtifact).where(
            StudyArtifact.subject_id == subject_id,
            StudyArtifact.kind == payload.kind,
            StudyArtifact.content_hash == digest,
        )
    )
    if cached_artifact is not None:
        return _to_response(cached_artifact, cached=True)

    generators = {
        "flashcards": generate_flashcard_draft,
        "concept_map": generate_concept_map_draft,
        "study_notes": generate_study_notes_draft,
    }
    try:
        draft = safe_call_ai(generators[payload.kind], passages, db=db)
    except GeminiNotConfigured:
        raise HTTPException(status_code=503, detail="إنشاء الأدوات الدراسية غير مهيأ حاليًا.") from None
    except GeminiRateLimited:
        raise HTTPException(status_code=429, detail="وصل المساعد إلى حد الطلبات. حاول لاحقًا.") from None
    except GeminiRequestFailed:
        raise HTTPException(status_code=502, detail="تعذر إنشاء الأداة الدراسية الآن. حاول مجددًا.") from None

    draft_content = draft.model_dump(mode="json")
    title = str(draft_content["title"])
    source_refs = [
        {
            "source_index": index,
            "resource_id": str(passage.resource_id),
            "file_name": passage.file_name,
            "page_number": passage.page_number,
        }
        for index, passage in enumerate(passages, start=1)
    ]
    artifact = StudyArtifact(
        subject_id=subject_id,
        created_by=profile.id,
        kind=payload.kind,
        title=title,
        content=draft_content,
        sources=source_refs,
        content_hash=digest,
        model=settings.gemini_model,
    )
    db.add(artifact)
    try:
        db.commit()
        db.refresh(artifact)
    except IntegrityError:
        db.rollback()
        cached_artifact = db.scalar(
            select(StudyArtifact).where(
                StudyArtifact.subject_id == subject_id,
                StudyArtifact.kind == payload.kind,
                StudyArtifact.content_hash == digest,
            )
        )
        if cached_artifact is not None:
            return _to_response(cached_artifact, cached=True)
        raise HTTPException(status_code=409, detail="تعذر حفظ الأداة الدراسية المتكررة.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="تعذر حفظ الأداة الدراسية.") from None
    return _to_response(artifact)
