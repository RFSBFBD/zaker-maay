import re
from datetime import datetime
from typing import Annotated
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes.resources import _accessible_subject
from app.core.auth import get_current_profile
from app.db.models import Subject, UserProfile, YouTubeLink
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/subjects/{subject_id}/youtube-links", tags=["youtube"])
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def parse_youtube_video_id(raw_url: str) -> str:
    try:
        parsed = urlsplit(raw_url.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid YouTube URL.") from None
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError("Only secure YouTube video links are supported.")

    segments = [part for part in parsed.path.split("/") if part]
    video_id = ""
    if host == "youtu.be" and len(segments) == 1:
        video_id = segments[0]
    elif host.endswith("youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif len(segments) == 2 and segments[0] in {"embed", "shorts", "live"}:
            video_id = segments[1]
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise ValueError("YouTube URL does not contain a valid video ID.")
    return video_id


class YouTubeLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2_048)

    @field_validator("url", mode="before")
    @classmethod
    def trim_url(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class YouTubeLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_id: UUID
    owner_id: UUID
    video_id: str
    url: str
    title: str | None
    created_at: datetime


def _get_subject(db: Session, subject_id: UUID, profile: UserProfile) -> Subject:
    try:
        return _accessible_subject(db, subject_id, profile)
    except HTTPException:
        raise


@router.get("", response_model=list[YouTubeLinkResponse])
def list_youtube_links(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[YouTubeLink]:
    _get_subject(db, subject_id, profile)
    return list(
        db.scalars(
            select(YouTubeLink)
            .where(YouTubeLink.subject_id == subject_id)
            .order_by(YouTubeLink.created_at.desc())
        ).all()
    )


@router.post("", response_model=YouTubeLinkResponse, status_code=status.HTTP_201_CREATED)
def add_youtube_link(
    subject_id: UUID,
    payload: YouTubeLinkCreate,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> YouTubeLink:
    _get_subject(db, subject_id, profile)
    try:
        video_id = parse_youtube_video_id(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    link = YouTubeLink(
        subject_id=subject_id,
        owner_id=profile.id,
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This video is already linked to the subject.") from None
    db.refresh(link)
    return link


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_youtube_link(
    subject_id: UUID,
    link_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    _get_subject(db, subject_id, profile)
    link = db.scalar(select(YouTubeLink).where(YouTubeLink.id == link_id, YouTubeLink.subject_id == subject_id))
    if link is None:
        raise HTTPException(status_code=404, detail="YouTube link not found.")
    if profile.role != "admin" and link.owner_id != profile.id:
        raise HTTPException(status_code=403, detail="Only the link owner or an admin can remove this video.")
    db.delete(link)
    db.commit()
