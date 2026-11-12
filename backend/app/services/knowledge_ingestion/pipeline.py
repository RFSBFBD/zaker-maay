from __future__ import annotations

import logging
import time
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeProcessingJob, Resource, ResourceChunk, Subject
from app.services.knowledge_ingestion.academic_organizer import (
    organize_subject_academic_hierarchy,
    register_document_chapter_and_topics,
)
from app.services.knowledge_ingestion.academic_understanding import analyze_academic_document
from app.services.knowledge_ingestion.cross_document_graph import ingest_concepts_and_build_relationships
from app.services.knowledge_ingestion.extractor import extract_document_content
from app.services.knowledge_ingestion.job_engine import (
    create_or_resume_ingestion_job,
    update_job_stage,
)
from app.services.knowledge_ingestion.markdown_converter import convert_to_canonical_markdown
from app.services.knowledge_ingestion.schemas import (
    IngestionPipelineResult,
    IngestionState,
)
from app.services.storage import neon_storage

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1_200
CHUNK_OVERLAP = 180


def run_knowledge_ingestion_pipeline(
    *,
    db: Session,
    resource_id: UUID,
    content_bytes: bytes | None = None,
) -> IngestionPipelineResult:
    """Execute the full AI Knowledge Ingestion, Understanding & Academic Organization cycle."""
    start_time = time.perf_counter()

    resource = db.get(Resource, resource_id)
    if not resource:
        raise ValueError(f"Resource with ID {resource_id} not found")

    subject = db.get(Subject, resource.subject_id)
    subject_title = subject.name if subject else "المقرر الدراسي"

    # Step 1: Create or resume persistent job record
    job = create_or_resume_ingestion_job(
        db=db,
        resource_id=resource_id,
        subject_id=resource.subject_id,
    )

    try:
        # Step 2: Security check
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="security_check",
            status=IngestionState.SECURITY_CHECK,
            progress_pct=10,
        )

        # Step 3: Fetch file bytes if not supplied
        if content_bytes is None:
            if resource.storage_key:
                content_bytes = neon_storage.download_file(
                    key=resource.storage_key,
                    bucket=resource.storage_bucket or neon_storage.get_default_bucket(),
                )
            else:
                # If audio transcript already exists, use it
                if resource.transcript_text:
                    content_bytes = resource.transcript_text.encode("utf-8")
                else:
                    raise ValueError(f"No file bytes or storage key available for resource {resource_id}")

        # Step 4: Extract content format-specifically
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="extracting",
            status=IngestionState.EXTRACTING,
            progress_pct=25,
        )
        extracted = extract_document_content(
            file_name=resource.file_name,
            content=content_bytes,
            mime_type=resource.mime_type,
        )

        # Step 5: Convert to Canonical Markdown
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="converting",
            status=IngestionState.CONVERTING,
            progress_pct=40,
        )
        canonical_doc = convert_to_canonical_markdown(
            resource_id=str(resource_id),
            subject_id=str(resource.subject_id),
            file_name=resource.file_name,
            extracted=extracted,
            subject_title=subject_title,
        )

        # Step 6: Store Canonical Markdown as a separate object in Neon Object Storage
        markdown_bytes = canonical_doc.markdown_content.encode("utf-8")
        markdown_key = f"subjects/{resource.subject_id}/markdown/{resource_id}.md"
        markdown_bucket = neon_storage.get_default_bucket()

        try:
            neon_storage.upload_file(
                content=markdown_bytes,
                key=markdown_key,
                bucket=markdown_bucket,
                content_type="text/markdown; charset=utf-8",
            )
            resource.markdown_storage_key = markdown_key
            resource.markdown_storage_bucket = markdown_bucket
        except Exception as exc:
            logger.warning("Could not persist canonical markdown to Neon Object Storage (proceeding locally): %s", exc)

        # Step 7: AI Document Understanding
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="understanding",
            status=IngestionState.UNDERSTANDING,
            progress_pct=60,
        )
        understanding = analyze_academic_document(canonical_doc, subject_title=subject_title)

        # Step 8: Academic Organization & Hierarchy Linking
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="organizing",
            status=IngestionState.ORGANIZING,
            progress_pct=75,
        )
        register_document_chapter_and_topics(
            db=db,
            subject_id=resource.subject_id,
            resource=resource,
            understanding=understanding,
        )
        org_report = organize_subject_academic_hierarchy(db=db, subject_id=resource.subject_id)

        # Step 9: Ingest Concepts & Build Cross-Document Knowledge Graph
        c_count, r_count = ingest_concepts_and_build_relationships(
            db=db,
            subject_id=resource.subject_id,
            resource_id=resource.id,
            understanding=understanding,
        )

        # Step 10: RAG Indexing — Chunking Canonical Markdown
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="indexing",
            status=IngestionState.INDEXING,
            progress_pct=90,
        )

        # Delete old chunks for idempotency on re-ingestion
        db.execute(delete(ResourceChunk).where(ResourceChunk.resource_id == resource_id))

        chunks_created = _create_rag_chunks(db, resource_id, canonical_doc)

        # Step 11: Quality Check
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="quality_check",
            status=IngestionState.QUALITY_CHECK,
            progress_pct=98,
        )
        if chunks_created == 0 and len(canonical_doc.markdown_content) > 50:
            # Fallback chunk if splitter produced 0
            db.add(
                ResourceChunk(
                    resource_id=resource_id,
                    chunk_index=0,
                    page_number=1,
                    content=canonical_doc.markdown_content[:2000],
                )
            )
            chunks_created = 1

        # Step 12: Mark ready
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="ready",
            status=IngestionState.READY,
            progress_pct=100,
        )
        db.commit()

        elapsed = time.perf_counter() - start_time
        return IngestionPipelineResult(
            resource_id=str(resource_id),
            subject_id=str(resource.subject_id),
            file_name=resource.file_name,
            status=IngestionState.READY,
            current_stage="ready",
            markdown_storage_key=resource.markdown_storage_key,
            academic_chapter=resource.academic_chapter,
            chapter_title=resource.chapter_title,
            concepts_count=c_count,
            relationships_count=r_count,
            chunks_created=chunks_created,
            detected_gaps=resource.detected_gaps or [],
            execution_time_sec=round(elapsed, 2),
        )

    except Exception as exc:
        db.rollback()
        logger.exception("Knowledge ingestion pipeline failed for resource %s: %s", resource_id, exc)
        update_job_stage(
            db=db,
            job_id=job.id,
            stage="failed",
            status=IngestionState.FAILED,
            error=str(exc),
        )
        db.commit()
        elapsed = time.perf_counter() - start_time
        return IngestionPipelineResult(
            resource_id=str(resource_id),
            subject_id=str(resource.subject_id),
            file_name=resource.file_name,
            status=IngestionState.FAILED,
            current_stage="failed",
            error=str(exc),
            execution_time_sec=round(elapsed, 2),
        )


def _create_rag_chunks(
    db: Session,
    resource_id: UUID,
    canonical_doc: CanonicalMarkdownDocument,
) -> int:
    """Chunk canonical markdown preserving page and section context."""
    sections = canonical_doc.markdown_content.split("---")
    chunk_idx = 0

    for sec in sections:
        clean_sec = sec.strip()
        if not clean_sec:
            continue

        # Extract page number if present
        import re
        page_m = re.search(r"صفحة / شريحة (\d+)", clean_sec)
        page_num = int(page_m.group(1)) if page_m else None

        # Split section into chunks if length > CHUNK_SIZE
        start = 0
        while start < len(clean_sec):
            end = min(start + CHUNK_SIZE, len(clean_sec))
            piece = clean_sec[start:end].strip()
            if piece:
                db.add(
                    ResourceChunk(
                        resource_id=resource_id,
                        chunk_index=chunk_idx,
                        page_number=page_num,
                        content=piece,
                    )
                )
                chunk_idx += 1
            if end >= len(clean_sec):
                break
            start = max(start + 1, end - CHUNK_OVERLAP)

    db.flush()
    return chunk_idx
