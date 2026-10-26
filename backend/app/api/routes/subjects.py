from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.db.models import Subject, SubjectMembership, UserProfile
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/subjects", tags=["subjects"])


class SubjectWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=10_000)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SubjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=10_000)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime


class MembershipWrite(BaseModel):
    user_id: UUID


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    subject_id: UUID
    role: str
    created_at: datetime


def _normalized_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def _accessible_subject(db: Session, subject_id: UUID, profile: UserProfile) -> Subject:
    query = select(Subject).where(Subject.id == subject_id, Subject.archived_at.is_(None))
    if profile.role != "admin":
        query = query.join(SubjectMembership).where(SubjectMembership.user_id == profile.id)
    subject = db.scalar(query)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")
    return subject


@router.get("", response_model=list[SubjectResponse])
def list_subjects(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Subject]:
    query = select(Subject).where(Subject.archived_at.is_(None)).order_by(Subject.name)
    if profile.role != "admin":
        query = query.join(SubjectMembership).where(SubjectMembership.user_id == profile.id)
    return list(db.scalars(query).all())


@router.get("/{subject_id}", response_model=SubjectResponse)
def get_subject(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> Subject:
    return _accessible_subject(db, subject_id, profile)


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectWrite,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> Subject:
    subject = Subject(
        name=payload.name,
        normalized_name=_normalized_name(payload.name),
        description=payload.description,
        created_by=profile.id,
    )
    db.add(subject)
    try:
        db.flush()
        # Automatically enroll creator in the subject
        membership = SubjectMembership(
            subject_id=subject.id,
            user_id=profile.id,
            role="owner" if profile.role == "admin" else "student",
        )
        db.add(membership)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A subject with this name already exists.") from None
    db.refresh(subject)
    return subject


@router.patch("/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: UUID,
    payload: SubjectPatch,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> Subject:
    subject = db.scalar(select(Subject).where(Subject.id == subject_id, Subject.archived_at.is_(None)))
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    if profile.role != "admin" and subject.created_by != profile.id:
        raise HTTPException(status_code=403, detail="Only subject owner or admin can update this subject.")
    if not payload.model_fields_set:
        raise HTTPException(status_code=422, detail="At least one field must be provided.")
    if "name" in payload.model_fields_set:
        if payload.name is None:
            raise HTTPException(status_code=422, detail="Subject name cannot be null.")
        subject.name = payload.name
        subject.normalized_name = _normalized_name(payload.name)
    if "description" in payload.model_fields_set:
        subject.description = payload.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A subject with this name already exists.") from None
    db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    subject = db.scalar(select(Subject).where(Subject.id == subject_id, Subject.archived_at.is_(None)))
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    if profile.role != "admin" and subject.created_by != profile.id:
        raise HTTPException(status_code=403, detail="Only subject owner or admin can archive this subject.")
    subject.archived_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{subject_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_subject_member(
    subject_id: UUID,
    payload: MembershipWrite,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> SubjectMembership:
    subject = db.scalar(select(Subject).where(Subject.id == subject_id, Subject.archived_at.is_(None)))
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    if profile.role != "admin" and subject.created_by != profile.id:
        raise HTTPException(status_code=403, detail="Admin or subject owner access required.")
    if db.get(UserProfile, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    membership = SubjectMembership(subject_id=subject_id, user_id=payload.user_id, role="student")
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User is already a member of this subject.") from None
    db.refresh(membership)
    return membership


@router.delete(
    "/{subject_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_subject_member(
    subject_id: UUID,
    user_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    subject = db.scalar(select(Subject).where(Subject.id == subject_id, Subject.archived_at.is_(None)))
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    if profile.role != "admin" and subject.created_by != profile.id:
        raise HTTPException(status_code=403, detail="Admin or subject owner access required.")
    membership = db.scalar(
        select(SubjectMembership).where(
            SubjectMembership.subject_id == subject_id,
            SubjectMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Subject membership not found.")
    db.delete(membership)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
