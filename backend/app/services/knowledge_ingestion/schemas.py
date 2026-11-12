from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IngestionState(str, Enum):
    UPLOADED = "uploaded"
    SECURITY_CHECK = "security_check"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    CONVERTING = "converting"
    UNDERSTANDING = "understanding"
    ORGANIZING = "organizing"
    INDEXING = "indexing"
    QUALITY_CHECK = "quality_check"
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class RelationshipType(str, Enum):
    PREREQUISITE_OF = "prerequisite_of"
    DEPENDS_ON = "depends_on"
    EXPANDS = "expands"
    EXPLAINS = "explains"
    REFERENCES = "references"
    COMPARES_WITH = "compares_with"
    DUPLICATES = "duplicates"
    POTENTIALLY_CONFLICTS_WITH = "potentially_conflicts_with"


class ExtractedPageContent(BaseModel):
    page_or_slide_number: int | None = None
    title: str | None = None
    text: str = ""
    headings: list[str] = Field(default_factory=list)
    tables: list[list[list[str]]] = Field(default_factory=list)
    speaker_notes: str | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    has_scanned_images: bool = False


class DocumentExtractionResult(BaseModel):
    file_name: str
    extension: str
    total_pages_or_slides: int = 0
    pages: list[ExtractedPageContent] = Field(default_factory=list)
    requires_ocr: bool = False
    is_audio: bool = False
    detected_language: str = "ar"
    raw_character_count: int = 0


class CanonicalMarkdownDocument(BaseModel):
    resource_id: str
    subject_id: str
    file_name: str
    title: str
    chapter_number: int | None = None
    markdown_content: str
    outline: list[str] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    tables_count: int = 0
    source_references: list[str] = Field(default_factory=list)


class ExtractedConceptItem(BaseModel):
    name: str
    definition: str
    concept_type: str = "concept"  # definition, process, algorithm, equation, classification, comparison
    page_or_slide_number: int | None = None
    source_excerpt: str = ""
    confidence_score: float = 1.0


class AcademicUnderstandingResult(BaseModel):
    subject_title: str
    detected_course: str = ""
    detected_chapter_number: int | None = None
    detected_chapter_title: str | None = None
    summary: str = ""
    learning_objectives: list[str] = Field(default_factory=list)
    topics: list[dict[str, Any]] = Field(default_factory=list)
    concepts: list[ExtractedConceptItem] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    identified_misconceptions: list[str] = Field(default_factory=list)
    academic_level: str = "undergraduate"


class ConceptRelationshipItem(BaseModel):
    source_concept_name: str
    target_concept_name: str
    relationship_type: RelationshipType
    description: str = ""
    conflict_details: str | None = None
    confidence_score: float = 1.0


class AcademicOrganizationReport(BaseModel):
    subject_id: str
    total_chapters_detected: int = 0
    ordered_chapters: list[dict[str, Any]] = Field(default_factory=list)
    detected_missing_chapters: list[int] = Field(default_factory=list)
    unclassified_resources: list[str] = Field(default_factory=list)


class IngestionPipelineResult(BaseModel):
    resource_id: str
    subject_id: str
    file_name: str
    status: IngestionState
    current_stage: str
    markdown_storage_key: str | None = None
    academic_chapter: int | None = None
    chapter_title: str | None = None
    concepts_count: int = 0
    relationships_count: int = 0
    chunks_created: int = 0
    detected_gaps: list[str] = Field(default_factory=list)
    execution_time_sec: float = 0.0
    error: str | None = None
