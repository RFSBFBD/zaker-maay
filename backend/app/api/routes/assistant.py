from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.db.models import UserProfile
from app.db.session import get_db
from app.services.ai_router import safe_call_ai
from app.services.gemini import (
    GeminiNotConfigured,
    GeminiRateLimited,
    GeminiRequestFailed,
    generate_grounded_answer,
)
from app.services.retrieval import RetrievedPassage, retrieve_for_subject
from app.api.routes.resources import _accessible_subject

router = APIRouter(prefix="/api/v1/subjects/{subject_id}", tags=["study assistant"])


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2_000)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SourceResponse(BaseModel):
    resource_id: UUID
    file_name: str
    page_number: int | None
    excerpt: str


class SearchResponse(BaseModel):
    results: list[SourceResponse]


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]


def _sources(passages: list[RetrievedPassage]) -> list[SourceResponse]:
    return [
        SourceResponse(
            resource_id=passage.resource_id,
            file_name=passage.file_name,
            page_number=passage.page_number,
            excerpt=passage.content[:500],
        )
        for passage in passages
    ]


@router.get("/resources/search", response_model=SearchResponse)
def search_resources(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=500)],
    limit: Annotated[int, Query(ge=1, le=8)] = 4,
) -> SearchResponse:
    _accessible_subject(db, subject_id, profile)
    passages = retrieve_for_subject(db, subject_id=subject_id, query=q, limit=limit)
    return SearchResponse(results=_sources(passages))


@router.post("/assistant/ask", response_model=AskResponse)
def ask_assistant(
    subject_id: UUID,
    payload: AskRequest,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> AskResponse:
    _accessible_subject(db, subject_id, profile)
    passages = retrieve_for_subject(db, subject_id=subject_id, query=payload.question)
    if not passages:
        return AskResponse(
            answer="لم أجد معلومات ذات صلة في الملفات النصية لهذه المادة. أضف ملفًا نصيًا أو PDF أو DOCX ثم حاول مجددًا.",
            sources=[],
        )
    try:
        answer = safe_call_ai(generate_grounded_answer, payload.question, passages, db=db)
    except GeminiNotConfigured:
        raise HTTPException(status_code=503, detail="المساعد الذكي غير مهيأ حاليًا.") from None
    except GeminiRateLimited:
        raise HTTPException(status_code=429, detail="وصل المساعد إلى حد الطلبات. حاول لاحقًا.") from None
    except GeminiRequestFailed:
        raise HTTPException(status_code=502, detail="تعذر إنشاء إجابة الآن. حاول مجددًا.") from None
    return AskResponse(answer=answer, sources=_sources(passages))
