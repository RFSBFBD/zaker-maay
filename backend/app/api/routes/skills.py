from __future__ import annotations

import logging
import re
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.db.models import AgentSkill, UserProfile
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/skills", tags=["admin_skills"])


def _require_admin(profile: UserProfile):
    if profile.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="صلاحية مسؤول النظام (Admin) مطلوبة لتنفيذ هذا الإجراء.",
        )


class IngestGitHubPayload(BaseModel):
    url: str | None = None
    github_url: str | None = None
    title: str | None = None
    skill_type: str = "pedagogy"

    @property
    def target_url(self) -> str:
        u = self.github_url or self.url or ""
        return u.strip()


class SkillUpdatePayload(BaseModel):
    title: str | None = None
    system_instructions: str | None = None
    is_active: bool | None = None
    skill_type: str | None = None


class SkillResponse(BaseModel):
    id: UUID
    title: str
    source_github_url: str | None
    system_instructions: str
    skill_type: str
    is_active: bool
    created_at: str
    updated_at: str


def _convert_to_raw_github_url(url: str) -> str:
    """Converts a standard github.com blob URL to a raw.githubusercontent.com URL."""
    cleaned = url.strip()
    # Match https://github.com/{owner}/{repo}/blob/{branch}/{path}
    match = re.match(r"^https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$", cleaned)
    if match:
        owner, repo, branch, path = match.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    return cleaned


@router.get("", response_model=list[SkillResponse])
def list_skills(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SkillResponse]:
    """List all AI agent skills imported from GitHub or created manually."""
    _require_admin(profile)
    skills = db.scalars(select(AgentSkill).order_by(AgentSkill.created_at.desc())).all()
    return [
        SkillResponse(
            id=s.id,
            title=s.title,
            source_github_url=s.source_github_url,
            system_instructions=s.system_instructions,
            skill_type=s.skill_type,
            is_active=s.is_active,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in skills
    ]


@router.post("/ingest-github", response_model=SkillResponse)
def ingest_github_skill(
    payload: IngestGitHubPayload,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> SkillResponse:
    """Fetch a skill/prompt from GitHub raw/blob URL, parse it, and save it as an active AgentSkill."""
    _require_admin(profile)

    if not payload.target_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="رابط GitHub مطلوب.",
        )

    raw_url = _convert_to_raw_github_url(payload.target_url)

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(raw_url)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"تعذر جلب الملف من GitHub (رمز الخطأ: {resp.status_code}). تأكد من صحة الرابط وأن المستودع عام (Public).",
                )
            content = resp.text.strip()
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل الاتصال بـ GitHub: {str(exc)}",
        ) from exc

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الملف الموجود في الرابط فارغ.",
        )

    # Derive title if not provided
    title = payload.title
    if not title:
        # Check first line for Markdown heading
        first_line = content.splitlines()[0].strip()
        if first_line.startswith("#"):
            title = first_line.lstrip("# ").strip()
        else:
            # Fallback to filename
            title = raw_url.split("/")[-1].replace(".md", "").replace(".txt", "").replace("-", " ").title()

    skill = AgentSkill(
        id=uuid4(),
        title=title[:200],
        source_github_url=payload.url[:512],
        system_instructions=content,
        skill_type=payload.skill_type,
        is_active=True,
        created_by=profile.id,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)

    logger.info("Admin %s ingested AI skill from GitHub: %s", profile.email, title)

    return SkillResponse(
        id=skill.id,
        title=skill.title,
        source_github_url=skill.source_github_url,
        system_instructions=skill.system_instructions,
        skill_type=skill.skill_type,
        is_active=skill.is_active,
        created_at=skill.created_at.isoformat(),
        updated_at=skill.updated_at.isoformat(),
    )


@router.patch("/{skill_id}", response_model=SkillResponse)
def update_skill(
    skill_id: UUID,
    payload: SkillUpdatePayload,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> SkillResponse:
    """Update or toggle active state of an AI agent skill."""
    _require_admin(profile)
    skill = db.get(AgentSkill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="المهارة غير موجودة.")

    if payload.title is not None:
        skill.title = payload.title.strip()[:200]
    if payload.system_instructions is not None:
        skill.system_instructions = payload.system_instructions.strip()
    if payload.is_active is not None:
        skill.is_active = payload.is_active
    if payload.skill_type is not None:
        skill.skill_type = payload.skill_type

    db.commit()
    db.refresh(skill)

    return SkillResponse(
        id=skill.id,
        title=skill.title,
        source_github_url=skill.source_github_url,
        system_instructions=skill.system_instructions,
        skill_type=skill.skill_type,
        is_active=skill.is_active,
        created_at=skill.created_at.isoformat(),
        updated_at=skill.updated_at.isoformat(),
    )


@router.delete("/{skill_id}")
def delete_skill(
    skill_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Delete an AI agent skill."""
    _require_admin(profile)
    skill = db.get(AgentSkill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="المهارة غير موجودة.")
    db.delete(skill)
    db.commit()
    return {"status": "ok", "message": "تم حذف المهارة بنجاح."}
