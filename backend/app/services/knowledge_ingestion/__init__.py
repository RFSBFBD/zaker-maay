from __future__ import annotations

from app.services.knowledge_ingestion.academic_organizer import (
    organize_subject_academic_hierarchy,
    register_document_chapter_and_topics,
)
from app.services.knowledge_ingestion.academic_understanding import analyze_academic_document
from app.services.knowledge_ingestion.batch_processor import (
    create_upload_batch,
    process_batch_upload,
    retry_failed_resource,
    synthesize_sequential_images_markdown,
)
from app.services.knowledge_ingestion.cross_document_graph import (
    get_concept_prerequisites,
    ingest_concepts_and_build_relationships,
)
from app.services.knowledge_ingestion.extractor import extract_document_content
from app.services.knowledge_ingestion.job_engine import (
    create_or_resume_ingestion_job,
    update_job_stage,
)
from app.services.knowledge_ingestion.markdown_converter import convert_to_canonical_markdown
from app.services.knowledge_ingestion.pipeline import run_knowledge_ingestion_pipeline
from app.services.knowledge_ingestion.schemas import (
    AcademicOrganizationReport,
    AcademicUnderstandingResult,
    CanonicalMarkdownDocument,
    DocumentExtractionResult,
    ExtractedConceptItem,
    IngestionPipelineResult,
    IngestionState,
    RelationshipType,
)

__all__ = [
    "run_knowledge_ingestion_pipeline",
    "create_upload_batch",
    "process_batch_upload",
    "retry_failed_resource",
    "synthesize_sequential_images_markdown",
    "extract_document_content",
    "convert_to_canonical_markdown",
    "analyze_academic_document",
    "organize_subject_academic_hierarchy",
    "register_document_chapter_and_topics",
    "ingest_concepts_and_build_relationships",
    "get_concept_prerequisites",
    "create_or_resume_ingestion_job",
    "update_job_stage",
    "AcademicOrganizationReport",
    "AcademicUnderstandingResult",
    "CanonicalMarkdownDocument",
    "DocumentExtractionResult",
    "ExtractedConceptItem",
    "IngestionPipelineResult",
    "IngestionState",
    "RelationshipType",
]
