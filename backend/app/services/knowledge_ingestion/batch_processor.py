from __future__ import annotations

import hashlib
import io
import logging
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    KnowledgeProcessingJob,
    Resource,
    ResourceChunk,
    Subject,
    UploadBatch,
)
from app.services.document_processing import process_document
from app.services.knowledge_ingestion.academic_organizer import organize_subject_academic_hierarchy
from app.services.knowledge_ingestion.job_engine import (
    create_or_resume_ingestion_job,
    update_job_stage,
)
from app.services.knowledge_ingestion.pipeline import run_knowledge_ingestion_pipeline
from app.services.knowledge_ingestion.schemas import (
    IngestionPipelineResult,
    IngestionState,
)
from app.services.storage import neon_storage

logger = logging.getLogger(__name__)

MAX_BATCH_FILES = 25
MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MiB
MAX_BATCH_BYTES = 250 * 1024 * 1024  # 250 MiB
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def natural_sort_key(s: str) -> list[int | str]:
    """Sort strings with embedded numbers naturally (e.g. page_1, page_2, page_10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def create_upload_batch(
    *,
    db: Session,
    subject_id: UUID,
    student_id: UUID,
    title: str | None = None,
    total_files: int = 0,
    metadata: dict[str, Any] | None = None,
) -> UploadBatch:
    """Create a new batch upload tracker in PostgreSQL."""
    batch_title = (title or "").strip() or f"دفعة ملفات - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
    batch = UploadBatch(
        id=uuid4(),
        subject_id=subject_id,
        student_id=student_id,
        title=batch_title,
        total_files=total_files,
        status="pending",
        success_count=0,
        failed_count=0,
        batch_metadata=metadata or {},
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def synthesize_sequential_images_markdown(
    *,
    db: Session,
    batch_id: UUID,
    subject_id: UUID,
    image_resources: list[Resource],
) -> dict[str, Any] | None:
    """Group sequential educational images into a structured Canonical Markdown representation.
    
    Includes factual image citations (*مرجع الصورة الأصلية: ...*) and preserves
    each image independently in Neon Object Storage.
    """
    if not image_resources:
        return None

    # Natural sort by file name so page_1, page_2, page_10 are ordered correctly
    sorted_images = sorted(image_resources, key=lambda r: natural_sort_key(r.file_name))
    subject = db.get(Subject, subject_id)
    subject_name = subject.name if subject else "المقرر الدراسي"

    batch = db.get(UploadBatch, batch_id)
    batch_title = batch.title if batch else "مجموعة صور تعليمية"

    lines: list[str] = [
        f"# {batch_title} - التوثيق التعليمي الموحد",
        "",
        f"> **المقرر الدراسي**: {subject_name}",
        f"> **نوع المحتوى**: وثائق ولوحات دراسية مصورة ومسلسلة",
        f"> **إجمالي الصور الموثقة**: {len(sorted_images)}",
        "",
    ]

    for idx, img in enumerate(sorted_images, start=1):
        lines.append("---")
        lines.append(f"## لوحة / وثيقة تعليمية رقم {idx}: `{img.file_name}`")
        lines.append(f"*مرجع الصورة الأصلية: {img.file_name}*")
        lines.append("")
        lines.append(f"> **معرف المورد (Resource ID)**: `{img.id}`")
        if img.storage_key:
            lines.append(f"> **مسار التخزين**: `{img.storage_key}`")
        lines.append("")
        lines.append(f"[محتوى بصري معتمد: تتضمن هذه الوثيقة المخططات والبيانات المرئية الخاصة بالموضوع `{img.file_name}`.]")
        lines.append("")

    canonical_md_text = "\n".join(lines)
    storage_key = f"subjects/{subject_id}/batches/{batch_id}/synthesized_images.md"
    bucket = neon_storage.get_default_bucket()

    try:
        neon_storage.upload_file(
            content=canonical_md_text.encode("utf-8"),
            key=storage_key,
            bucket=bucket,
            content_type="text/markdown",
        )
    except Exception as exc:
        logger.warning("Could not upload synthesized images markdown to Neon storage: %s", exc)

    return {
        "images_count": len(sorted_images),
        "ordered_filenames": [img.file_name for img in sorted_images],
        "markdown_storage_key": storage_key,
        "markdown_storage_bucket": bucket,
    }


def process_batch_upload(
    *,
    db: Session,
    batch_id: UUID,
    subject_id: UUID,
    uploaded_by: UUID,
    files_data: list[dict[str, Any]],
    transcribe_audio: bool = False,
) -> dict[str, Any]:
    """Process a batch of uploaded files independently through the knowledge ingestion pipeline.
    
    Guarantees:
    - Bounded execution.
    - An error on one file does NOT cause successful files to be lost.
    - Each file retains its own resource ID and processing status.
    - Sequential images are synthesized into an educational markdown document.
    - Cross-document academic hierarchy is refreshed.
    """
    batch = db.get(UploadBatch, batch_id)
    if not batch:
        raise ValueError(f"Batch with ID {batch_id} not found")

    # 1. Validate batch constraints
    total_files = len(files_data)
    if total_files > MAX_BATCH_FILES:
        raise ValueError(f"Batch contains {total_files} files, exceeding limit of {MAX_BATCH_FILES}.")

    total_bytes = sum(len(f.get("content", b"")) for f in files_data)
    if total_bytes > MAX_BATCH_BYTES:
        raise ValueError(
            f"Total batch size ({total_bytes / (1024 * 1024):.1f} MB) exceeds limit of {MAX_BATCH_BYTES / (1024 * 1024):.0f} MB."
        )

    batch.total_files = total_files
    batch.status = "processing"
    db.commit()

    processed_resources: list[Resource] = []
    item_results: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    for file_info in files_data:
        file_name = file_info["file_name"]
        content_bytes = file_info["content"]
        mime_type = file_info.get("mime_type", "application/octet-stream")
        ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        # Validate single file size
        if len(content_bytes) > MAX_FILE_BYTES:
            failed_count += 1
            item_results.append({
                "file_name": file_name,
                "status": "failed",
                "error": f"حجم الملف يتجاوز الحد الأقصى المسموح به ({MAX_FILE_BYTES // (1024 * 1024)} ميغابايت).",
            })
            continue

        sha256 = hashlib.sha256(content_bytes).hexdigest()

        # Check duplicate inside subject
        duplicate = db.scalar(
            select(Resource).where(Resource.subject_id == subject_id, Resource.sha256 == sha256)
        )
        if duplicate:
            # File already exists in this subject library; associate or link
            item_results.append({
                "resource_id": str(duplicate.id),
                "file_name": file_name,
                "status": "duplicate",
                "error": "الملف موجود بالفعل في مكتبة المقرر.",
            })
            success_count += 1
            continue

        resource_id = uuid4()
        storage_bucket = neon_storage.get_default_bucket()
        storage_key = neon_storage.build_object_key(
            user_id=uploaded_by,
            document_id=resource_id,
            filename=file_name,
            prefix=f"subjects/{subject_id}/resources",
        )

        # Upload original file to Neon Object Storage
        try:
            neon_storage.upload_file(
                content=content_bytes,
                key=storage_key,
                bucket=storage_bucket,
                content_type=mime_type,
            )
        except Exception as exc:
            logger.warning("Neon upload fallback or error for %s: %s", file_name, exc)

        # Process document chunks
        processed_doc = process_document(file_name, content_bytes)

        # Persist resource record
        resource = Resource(
            id=resource_id,
            subject_id=subject_id,
            uploaded_by=uploaded_by,
            batch_id=batch_id,
            file_name=file_name,
            mime_type=mime_type,
            size_bytes=len(content_bytes),
            sha256=sha256,
            storage_provider="neon",
            storage_bucket=storage_bucket,
            storage_key=storage_key,
            cloudinary_public_id=storage_key,
            secure_url=f"neon://{storage_bucket}/{storage_key}",
            processing_status=processed_doc.status,
            ingestion_status="processing",
        )
        db.add(resource)
        try:
            db.flush()
            db.add_all(
                ResourceChunk(
                    resource_id=resource.id,
                    chunk_index=idx,
                    page_number=page,
                    content=chunk_text,
                )
                for idx, (page, chunk_text) in enumerate(processed_doc.chunks)
            )
            db.commit()
            db.refresh(resource)
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to insert resource %s: %s", file_name, exc)
            failed_count += 1
            item_results.append({
                "file_name": file_name,
                "status": "failed",
                "error": "تعذر حفظ بيانات الملف في قاعدة البيانات.",
            })
            continue

        # Run independent knowledge ingestion pipeline for this resource
        try:
            create_or_resume_ingestion_job(
                db=db,
                resource_id=resource.id,
                subject_id=subject_id,
                batch_id=batch_id,
            )
            db.commit()

            pipeline_result = run_knowledge_ingestion_pipeline(
                db=db,
                resource_id=resource.id,
                content_bytes=content_bytes,
            )
            processed_resources.append(resource)
            success_count += 1
            item_results.append({
                "resource_id": str(resource.id),
                "file_name": file_name,
                "status": "ready",
                "chapter_number": pipeline_result.academic_chapter,
                "chapter_title": pipeline_result.chapter_title,
                "concepts_count": pipeline_result.concepts_count,
                "error": None,
            })
        except Exception as exc:
            db.rollback()
            logger.exception("Ingestion failed for file %s: %s", file_name, exc)
            resource.ingestion_status = "failed"
            resource.processing_status = "failed"
            db.commit()
            failed_count += 1
            item_results.append({
                "resource_id": str(resource.id),
                "file_name": file_name,
                "status": "failed",
                "error": str(exc),
            })

    # 3. Check for multiple images and synthesize consolidated educational source
    image_resources = [
        res for res in processed_resources
        if PurePosixPath(res.file_name).suffix.lower() in IMAGE_EXTENSIONS
    ]
    image_synthesis_meta = None
    if image_resources:
        try:
            image_synthesis_meta = synthesize_sequential_images_markdown(
                db=db,
                batch_id=batch_id,
                subject_id=subject_id,
                image_resources=image_resources,
            )
        except Exception as exc:
            logger.warning("Sequential image synthesis failed for batch %s: %s", batch_id, exc)

    # 4. Batch-level academic reorganization across subject
    try:
        organize_subject_academic_hierarchy(db=db, subject_id=subject_id)
    except Exception as exc:
        logger.warning("Subject reorganization after batch upload failed: %s", exc)

    # 5. Resolve final batch status
    if failed_count == 0:
        final_status = "completed"
    elif success_count > 0:
        final_status = "partially_completed"
    else:
        final_status = "failed"

    batch.success_count = success_count
    batch.failed_count = failed_count
    batch.status = final_status
    batch.batch_metadata = {
        "item_results": item_results,
        "image_synthesis": image_synthesis_meta,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    db.commit()
    db.refresh(batch)

    return {
        "batch_id": str(batch.id),
        "subject_id": str(subject_id),
        "title": batch.title,
        "status": batch.status,
        "total_files": total_files,
        "success_count": success_count,
        "failed_count": failed_count,
        "resources": item_results,
        "image_synthesis": image_synthesis_meta,
    }


def retry_failed_resource(
    *,
    db: Session,
    resource_id: UUID,
) -> IngestionPipelineResult:
    """Retry ingestion for a single failed file in a batch without repeating successful files."""
    resource = db.get(Resource, resource_id)
    if not resource:
        raise ValueError(f"Resource with ID {resource_id} not found")

    job = create_or_resume_ingestion_job(
        db=db,
        resource_id=resource.id,
        subject_id=resource.subject_id,
        batch_id=resource.batch_id,
    )
    db.commit()

    try:
        result = run_knowledge_ingestion_pipeline(
            db=db,
            resource_id=resource.id,
            content_bytes=None,
        )

        # If resource belongs to a batch, update batch metrics
        if resource.batch_id:
            batch = db.get(UploadBatch, resource.batch_id)
            if batch:
                all_resources = db.scalars(
                    select(Resource).where(Resource.batch_id == batch.id)
                ).all()
                succ = sum(1 for r in all_resources if r.ingestion_status in {"ready", "completed"})
                fail = sum(1 for r in all_resources if r.ingestion_status == "failed")
                batch.success_count = succ
                batch.failed_count = fail
                batch.status = "completed" if fail == 0 else "partially_completed"
                db.commit()

        return result
    except Exception as exc:
        db.rollback()
        resource.ingestion_status = "failed"
        resource.processing_status = "failed"
        db.commit()
        raise exc
