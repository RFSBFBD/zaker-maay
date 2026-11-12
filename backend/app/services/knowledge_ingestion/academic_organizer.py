from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AcademicChapter, AcademicTopic, Resource
from app.services.knowledge_ingestion.schemas import (
    AcademicOrganizationReport,
    AcademicUnderstandingResult,
)

logger = logging.getLogger(__name__)


def organize_subject_academic_hierarchy(
    db: Session,
    subject_id: UUID,
) -> AcademicOrganizationReport:
    """Analyze all resources in a subject, organize chapters logically, and identify missing sequence gaps."""
    resources = db.scalars(
        select(Resource)
        .where(Resource.subject_id == subject_id)
        .order_by(Resource.created_at.asc())
    ).all()

    # Collect all chapters
    chapter_map: dict[int, list[Resource]] = {}
    unclassified: list[str] = []

    for r in resources:
        ch_num = r.academic_chapter
        if ch_num is not None:
            chapter_map.setdefault(ch_num, []).append(r)
        else:
            unclassified.append(r.file_name)

    # Sort detected chapter numbers
    detected_chapter_numbers = sorted(chapter_map.keys())

    # Detect gaps in chapter sequence: e.g. [1, 2, 4] -> missing [3]
    missing_chapters: list[int] = []
    if detected_chapter_numbers:
        min_ch = min(detected_chapter_numbers)
        max_ch = max(detected_chapter_numbers)
        # Only check gaps if min_ch is reasonable (e.g. 1 or 2)
        if min_ch <= 2:
            for expected in range(min_ch, max_ch + 1):
                if expected not in chapter_map:
                    missing_chapters.append(expected)

    # Update or insert into academic_chapters table
    ordered_chapters: list[dict[str, Any]] = []

    for order_idx, ch_num in enumerate(detected_chapter_numbers, start=1):
        res_list = chapter_map[ch_num]
        first_res = res_list[0]
        derived_title = first_res.chapter_title or f"الفصل {ch_num}"

        # Look for existing chapter in DB
        db_chapter = db.scalar(
            select(AcademicChapter).where(
                AcademicChapter.subject_id == subject_id,
                AcademicChapter.chapter_number == ch_num,
            )
        )
        if not db_chapter:
            db_chapter = AcademicChapter(
                id=uuid4(),
                subject_id=subject_id,
                chapter_number=ch_num,
                title=derived_title,
                summary=f"فصل دراسي رقم {ch_num} يضم {len(res_list)} مراجع تعليمية.",
                order_index=order_idx,
            )
            db.add(db_chapter)
            db.flush()
        else:
            db_chapter.order_index = order_idx
            if not db_chapter.title or db_chapter.title.startswith("الفصل"):
                db_chapter.title = derived_title

        ordered_chapters.append({
            "chapter_id": str(db_chapter.id),
            "chapter_number": ch_num,
            "title": db_chapter.title,
            "documents_count": len(res_list),
            "documents": [r.file_name for r in res_list],
            "order_index": order_idx,
        })

    # Record detected gaps in each resource metadata
    if missing_chapters:
        gap_strs = [f"الفصل {g} غير متوفر في مكتبة المادة حالياً" for g in missing_chapters]
        for r in resources:
            r.detected_gaps = gap_strs
    else:
        for r in resources:
            r.detected_gaps = []

    return AcademicOrganizationReport(
        subject_id=str(subject_id),
        total_chapters_detected=len(detected_chapter_numbers),
        ordered_chapters=ordered_chapters,
        detected_missing_chapters=missing_chapters,
        unclassified_resources=unclassified,
    )


def register_document_chapter_and_topics(
    *,
    db: Session,
    subject_id: UUID,
    resource: Resource,
    understanding: AcademicUnderstandingResult,
) -> AcademicChapter | None:
    """Register or link document to its verified academic chapter and create topics."""
    ch_num = understanding.detected_chapter_number
    ch_title = understanding.detected_chapter_title or resource.file_name

    resource.academic_chapter = ch_num
    resource.chapter_title = ch_title

    db_chapter = None
    if ch_num is not None:
        db_chapter = db.scalar(
            select(AcademicChapter).where(
                AcademicChapter.subject_id == subject_id,
                AcademicChapter.chapter_number == ch_num,
            )
        )
        if not db_chapter:
            db_chapter = AcademicChapter(
                id=uuid4(),
                subject_id=subject_id,
                chapter_number=ch_num,
                title=ch_title,
                summary=understanding.summary,
                learning_objectives=understanding.learning_objectives,
                order_index=ch_num,
            )
            db.add(db_chapter)
            db.flush()

    # Register topics
    for t_idx, topic_data in enumerate(understanding.topics, start=1):
        t_title = topic_data.get("title", "").strip()
        if not t_title:
            continue
        norm_title = t_title.lower()

        existing_topic = db.scalar(
            select(AcademicTopic).where(
                AcademicTopic.subject_id == subject_id,
                AcademicTopic.normalized_title == norm_title,
            )
        )
        if not existing_topic:
            new_topic = AcademicTopic(
                id=uuid4(),
                subject_id=subject_id,
                chapter_id=db_chapter.id if db_chapter else None,
                title=t_title,
                normalized_title=norm_title,
                summary=topic_data.get("summary"),
                is_foundational=topic_data.get("is_foundational", False),
                order_index=t_idx,
            )
            db.add(new_topic)

    db.flush()
    return db_chapter
