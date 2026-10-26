from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.db.models import StudentInquiry, Subject, UserProfile
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/inquiries", tags=["inquiries"])


class StudentInquiryItem(BaseModel):
    id: UUID
    subject_id: UUID
    subject_name: str
    question: str
    ai_suggested_answer: str | None
    status: str  # pending, approved, rejected
    admin_answer: str | None
    admin_notes: str | None
    is_read: bool
    created_at: datetime
    answered_at: datetime | None


class StudentInquiriesResponse(BaseModel):
    inquiries: list[StudentInquiryItem]
    unread_count: int


class AdminInquiryItem(BaseModel):
    id: UUID
    subject_id: UUID
    subject_name: str
    student_id: UUID
    student_email: str | None
    student_name: str | None
    question: str
    ai_suggested_answer: str | None
    status: str
    admin_answer: str | None
    admin_notes: str | None
    created_at: datetime
    answered_at: datetime | None


class AdminRespondPayload(BaseModel):
    status: str  # approved, rejected
    admin_answer: str | None = None
    admin_notes: str | None = None


# ── Student Endpoints ───────────────────────────────────────────────

@router.get("/me", response_model=StudentInquiriesResponse)
def get_my_inquiries(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> StudentInquiriesResponse:
    """Return all inquiries asked by the current student with unread notification count."""
    rows = db.execute(
        select(StudentInquiry, Subject.name.label("subject_name"))
        .join(Subject, StudentInquiry.subject_id == Subject.id)
        .where(StudentInquiry.student_id == profile.id)
        .order_by(desc(StudentInquiry.created_at))
    ).all()

    inquiries = [
        StudentInquiryItem(
            id=inq.id,
            subject_id=inq.subject_id,
            subject_name=subj_name,
            question=inq.question,
            ai_suggested_answer=inq.ai_suggested_answer,
            status=inq.status,
            admin_answer=inq.admin_answer,
            admin_notes=inq.admin_notes,
            is_read=inq.is_read,
            created_at=inq.created_at,
            answered_at=inq.answered_at,
        )
        for inq, subj_name in rows
    ]

    unread = sum(
        1 for item in inquiries if not item.is_read and item.status in ("approved", "rejected")
    )
    return StudentInquiriesResponse(inquiries=inquiries, unread_count=unread)


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
def mark_all_read(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
):
    """Mark all answered inquiries as read for the student."""
    inquiries = db.scalars(
        select(StudentInquiry).where(
            StudentInquiry.student_id == profile.id,
            StudentInquiry.is_read.is_(False),
            StudentInquiry.status.in_(["approved", "rejected"]),
        )
    ).all()
    for inq in inquiries:
        inq.is_read = True
    db.commit()
    return {"ok": True, "marked": len(inquiries)}


# ── Admin Endpoints ────────────────────────────────────────────────

@router.get("/admin/all", response_model=list[AdminInquiryItem])
def get_admin_inquiries(
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: str | None = None,
) -> list[AdminInquiryItem]:
    """Admin view: List student inquiries across all subjects."""
    if profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    query = (
        select(
            StudentInquiry,
            Subject.name.label("subject_name"),
            UserProfile.email.label("student_email"),
            UserProfile.display_name.label("student_name"),
        )
        .join(Subject, StudentInquiry.subject_id == Subject.id)
        .join(UserProfile, StudentInquiry.student_id == UserProfile.id)
        .order_by(desc(StudentInquiry.created_at))
    )

    if status_filter:
        query = query.where(StudentInquiry.status == status_filter)

    rows = db.execute(query).all()
    return [
        AdminInquiryItem(
            id=inq.id,
            subject_id=inq.subject_id,
            subject_name=subj_name,
            student_id=inq.student_id,
            student_email=student_email,
            student_name=student_name,
            question=inq.question,
            ai_suggested_answer=inq.ai_suggested_answer,
            status=inq.status,
            admin_answer=inq.admin_answer,
            admin_notes=inq.admin_notes,
            created_at=inq.created_at,
            answered_at=inq.answered_at,
        )
        for inq, subj_name, student_email, student_name in rows
    ]


@router.post("/admin/{inquiry_id}/respond", response_model=AdminInquiryItem)
def respond_to_inquiry(
    inquiry_id: UUID,
    payload: AdminRespondPayload,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminInquiryItem:
    """Admin response: approve & provide official answer, or reject out-of-scope question."""
    if profile.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    inq = db.scalar(select(StudentInquiry).where(StudentInquiry.id == inquiry_id))
    if not inq:
        raise HTTPException(status_code=404, detail="Inquiry not found.")

    if payload.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be approved or rejected.")

    inq.status = payload.status
    if payload.admin_answer is not None:
        inq.admin_answer = payload.admin_answer.strip()
    if payload.admin_notes is not None:
        inq.admin_notes = payload.admin_notes.strip()
    inq.answered_at = datetime.now()
    inq.is_read = False  # trigger notification for student
    db.commit()

    subj = db.scalar(select(Subject).where(Subject.id == inq.subject_id))
    student = db.scalar(select(UserProfile).where(UserProfile.id == inq.student_id))

    return AdminInquiryItem(
        id=inq.id,
        subject_id=inq.subject_id,
        subject_name=subj.name if subj else "",
        student_id=inq.student_id,
        student_email=student.email if student else None,
        student_name=student.display_name if student else None,
        question=inq.question,
        ai_suggested_answer=inq.ai_suggested_answer,
        status=inq.status,
        admin_answer=inq.admin_answer,
        admin_notes=inq.admin_notes,
        created_at=inq.created_at,
        answered_at=inq.answered_at,
    )
