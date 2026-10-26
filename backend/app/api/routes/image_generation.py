from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.db.models import UserProfile
from app.db.session import get_db
from app.services import gemini

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/subjects/{subject_id}/images", tags=["image_generation"])


def _accessible_subject(db: Session, subject_id: UUID, profile: UserProfile):
    from app.api.routes.subjects import _accessible_subject as sub_acc
    return sub_acc(db, subject_id, profile)


class ImageGeneratePayload(BaseModel):
    prompt: str = Field(min_length=2, max_length=500)
    context: str | None = Field(default=None, max_length=2000)


class ImageGenerateResponse(BaseModel):
    type: str  # "image" (base64 data url) or "svg" (raw svg markup)
    title: str
    description: str
    image_url: str | None = None
    svg: str | None = None


@router.post("/generate", response_model=ImageGenerateResponse)
def generate_educational_image(
    subject_id: UUID,
    payload: ImageGeneratePayload,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> ImageGenerateResponse:
    """Generate an educational visual diagram or concept illustration (Nano Banana / Imagen / Smart SVG)."""
    _accessible_subject(db, subject_id, profile)

    try:
        result = gemini.generate_concept_illustration(
            prompt=payload.prompt,
            context=payload.context or "",
            db=db,
        )
        return ImageGenerateResponse(
            type=result.get("type", "svg"),
            title=result.get("title", payload.prompt),
            description=result.get("description", payload.prompt),
            image_url=result.get("image_url"),
            svg=result.get("svg"),
        )
    except gemini.GeminiNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="خدمة توليد الصور (نانو بنانا / Imagen) غير مهيأة. أضف مفتاح API في لوحة الإدارة.",
        ) from None
    except gemini.GeminiRateLimited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تم تجاوز حد الطلبات مؤقتاً لتوليد الصور. حاول لاحقاً.",
        ) from None
    except Exception as exc:
        logger.warning("Educational image generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="تعذر إنشاء الرسم التوضيحي بالذكاء الاصطناعي حالياً.",
        ) from None
