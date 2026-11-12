from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeProcessingJob, Resource
from app.services.knowledge_ingestion.schemas import IngestionState

logger = logging.getLogger(__name__)


def create_or_resume_ingestion_job(
    *,
    db: Session,
    resource_id: UUID,
    subject_id: UUID,
    batch_id: UUID | None = None,
) -> KnowledgeProcessingJob:
    """Create a new job tracker or resume an interrupted job."""
    resource = db.get(Resource, resource_id)
    resolved_batch_id = batch_id or (resource.batch_id if resource else None)

    existing = db.scalar(
        select(KnowledgeProcessingJob).where(
            KnowledgeProcessingJob.resource_id == resource_id,
        )
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.retry_count = (existing.retry_count or 0) + 1
        existing.status = IngestionState.QUEUED.value
        existing.current_stage = "queued"
        existing.progress_pct = 5
        existing.error_message = None
        existing.started_at = now
        if resolved_batch_id and not existing.batch_id:
            existing.batch_id = resolved_batch_id
        db.flush()
        return existing

    job = KnowledgeProcessingJob(
        id=uuid4(),
        resource_id=resource_id,
        subject_id=subject_id,
        batch_id=resolved_batch_id,
        status=IngestionState.UPLOADED.value,
        current_stage="uploaded",
        progress_pct=0,
        retry_count=0,
        started_at=now,
    )
    db.add(job)
    db.flush()
    return job


def update_job_stage(
    *,
    db: Session,
    job_id: UUID,
    stage: str,
    status: IngestionState = IngestionState.QUEUED,
    progress_pct: int = 0,
    error: str | None = None,
) -> None:
    """Update progress stage of an ingestion job."""
    job = db.get(KnowledgeProcessingJob, job_id)
    if not job:
        return

    job.current_stage = stage
    job.status = status.value
    job.progress_pct = max(job.progress_pct, progress_pct)
    if error:
        job.error_message = error

    if status in (IngestionState.READY, IngestionState.FAILED, IngestionState.NEEDS_REVIEW):
        job.completed_at = datetime.now(timezone.utc)

    # Sync with resource ingestion_status
    resource = db.get(Resource, job.resource_id)
    if resource:
        resource.ingestion_status = status.value
        if status == IngestionState.READY:
            resource.processing_status = "ready"
        elif status == IngestionState.FAILED:
            resource.processing_status = "failed"

    db.flush()
