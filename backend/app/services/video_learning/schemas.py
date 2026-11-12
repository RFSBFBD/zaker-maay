from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class VideoProcessingState(str, Enum):
    SUBMITTED = "submitted"
    VALIDATING = "validating"
    PROCESSING = "processing"
    METADATA_EXTRACTION = "metadata_extraction"
    TRANSCRIPT_EXTRACTION = "transcript_extraction"
    AUDIO_PROCESSING = "audio_processing"
    FRAME_EXTRACTION = "frame_extraction"
    VISUAL_ANALYSIS = "visual_analysis"
    MULTIMODAL_UNDERSTANDING = "multimodal_understanding"
    MARKDOWN_GENERATION = "markdown_generation"
    KNOWLEDGE_EXTRACTION = "knowledge_extraction"
    INDEXING = "indexing"
    QUALITY_CHECK = "quality_check"
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    NO_CAPTIONS = "no_captions"


class VisualCategory(str, Enum):
    SLIDE = "slide"
    DIAGRAM = "diagram"
    NETWORK_TOPOLOGY = "network_topology"
    CODE_SNIPPET = "code"
    EQUATION = "equation"
    WHITEBOARD = "whiteboard"
    DEMONSTRATION = "demonstration"
    GENERAL = "general"


class TimestampedTranscriptSegment(BaseModel):
    text: str
    start_seconds: float
    duration_seconds: float = 0.0
    end_seconds: float = 0.0
    speaker: str | None = None
    confidence: float = 1.0


class VisualObservation(BaseModel):
    timestamp_seconds: float
    category: VisualCategory = VisualCategory.GENERAL
    title: str
    description: str
    on_screen_labels: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    is_uncertain: bool = False


class VideoSegment(BaseModel):
    segment_index: int
    title: str
    start_seconds: float
    end_seconds: float
    transcript_text: str
    visual_observations: list[VisualObservation] = Field(default_factory=list)
    concepts_covered: list[str] = Field(default_factory=list)


class VideoMetadata(BaseModel):
    video_id: str
    url: str
    provider: str = "youtube"
    title: str
    description: str | None = None
    channel_name: str | None = None
    duration_seconds: int = 0
    published_at: datetime | None = None
    detected_language: str = "ar"
    chapters: list[dict[str, Any]] = Field(default_factory=list)


class CanonicalVideoDocument(BaseModel):
    video_id: str
    title: str
    metadata: VideoMetadata
    overview: str
    main_topics: list[dict[str, Any]] = Field(default_factory=list)
    segments: list[VideoSegment] = Field(default_factory=list)
    diagrams_and_visuals: list[VisualObservation] = Field(default_factory=list)
    equations_and_code: list[dict[str, Any]] = Field(default_factory=list)
    key_terminology: list[dict[str, str]] = Field(default_factory=list)
    concept_relationships: list[dict[str, Any]] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    markdown_content: str


class VideoProcessingResult(BaseModel):
    video_id: str
    subject_id: str
    status: VideoProcessingState
    title: str
    channel_name: str | None = None
    duration_seconds: int = 0
    language: str = "ar"
    has_captions: bool = False
    segments_count: int = 0
    concepts_count: int = 0
    visual_analysis_status: str = "ready"
    markdown_storage_key: str | None = None
    error: str | None = None
