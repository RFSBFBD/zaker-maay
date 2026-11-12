from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from pypdf import PdfWriter
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    ConceptRelationship,
    ExtractedConcept,
    Resource,
    ResourceChunk,
    Subject,
    SubjectMembership,
    UserProfile,
    YouTubeChunk,
    YouTubeLink,
)
from app.services.retrieval import retrieve_for_subject
from app.services.study_agent.tool_registry import TenantAccessDenied, ToolRegistry
from app.services.video_learning.metadata import (
    build_youtube_timestamp_url,
    fetch_video_metadata,
    format_timestamp,
    parse_youtube_video_id,
)
from app.services.video_learning.pipeline import process_video_learning
from app.services.video_learning.schemas import (
    TimestampedTranscriptSegment,
    VideoMetadata,
    VideoProcessingState,
    VisualCategory,
)
from app.services.video_learning.transcript import (
    detect_transcript_language,
    fetch_timestamped_transcript,
    group_transcript_into_lesson_sections,
)
from app.services.video_learning.visual_analyzer import extract_visual_observations_from_lesson


@pytest.fixture
def video_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()

    student = UserProfile(id=uuid.uuid4(), email="student@video.test", role="student", skill_level=4)
    other_student = UserProfile(id=uuid.uuid4(), email="other@video.test", role="student", skill_level=2)
    subject = Subject(id=uuid.uuid4(), name="شبكات الحاسب", created_by=student.id)
    membership = SubjectMembership(user_id=student.id, subject_id=subject.id, role="student")
    session.add_all([student, other_student, subject, membership])
    session.commit()

    try:
        yield session, student, other_student, subject
    finally:
        session.close()


# ── 1. URL Validation & Parsing ───────────────────────────────────────────────

def test_parse_youtube_video_id_valid_formats():
    """Verify standard watch URLs, short URLs, and embed URLs."""
    assert parse_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_youtube_video_id("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == "dQw4w9WgXcQ"
    assert parse_youtube_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_parse_youtube_video_id_invalid_and_ssrf_rejection():
    """Verify rejection of insecure HTTP, non-YouTube domains, SSRF attacks, and malformed IDs."""
    with pytest.raises(ValueError, match="Only secure YouTube"):
        parse_youtube_video_id("http://www.youtube.com/watch?v=dQw4w9WgXcQ")

    with pytest.raises(ValueError, match="Only secure YouTube"):
        parse_youtube_video_id("https://vimeo.com/123456789")

    with pytest.raises(ValueError, match="Only secure YouTube"):
        parse_youtube_video_id("https://attacker.com/evil.php?url=https://youtube.com")

    with pytest.raises(ValueError, match="valid 11-character"):
        parse_youtube_video_id("https://www.youtube.com/watch?v=short")


# ── 2. Timestamp Formatting & URL Generation ──────────────────────────────────

def test_timestamp_formatting_and_urls():
    assert format_timestamp(45) == "00:45"
    assert format_timestamp(515) == "08:35"
    assert format_timestamp(3665) == "01:01:05"

    url = build_youtube_timestamp_url("abc123xyz78", 515)
    assert url == "https://www.youtube.com/watch?v=abc123xyz78&t=515s"


# ── 3. Language & Transcript Detection ────────────────────────────────────────

def test_language_detection():
    assert detect_transcript_language("هذا شرح مفصل لطبقات الشبكة ونموذج OSI") == "ar"
    assert detect_transcript_language("In this lecture we discuss TCP three way handshake") == "en"


def test_group_transcript_into_lesson_sections():
    raw_segments = [
        TimestampedTranscriptSegment(text="Welcome everyone.", start_seconds=0.0, duration_seconds=10.0, end_seconds=10.0),
        TimestampedTranscriptSegment(text="Today we cover TCP.", start_seconds=10.0, duration_seconds=25.0, end_seconds=35.0),
        TimestampedTranscriptSegment(text="And also UDP protocol.", start_seconds=35.0, duration_seconds=30.0, end_seconds=65.0),
        TimestampedTranscriptSegment(text="Let us begin with diagrams.", start_seconds=65.0, duration_seconds=20.0, end_seconds=85.0),
    ]
    sections = group_transcript_into_lesson_sections(raw_segments, window_duration_seconds=60.0)
    assert len(sections) == 2
    assert sections[0]["start_seconds"] == 0.0
    assert sections[0]["end_seconds"] == 65.0
    assert "Welcome everyone." in sections[0]["text"]
    assert "Today we cover TCP." in sections[0]["text"]


# ── 4. Visual Understanding & Observation Extraction ──────────────────────────

def test_visual_observations_extraction():
    segments = [
        TimestampedTranscriptSegment(text="نبدأ بمخطط الشبكة التوضيحي Network Topology", start_seconds=15.0, duration_seconds=10.0, end_seconds=25.0),
        TimestampedTranscriptSegment(text="كما نرى في هذا الكود البرمجي في لغة بايثون def socket_connect", start_seconds=70.0, duration_seconds=15.0, end_seconds=85.0),
        TimestampedTranscriptSegment(text="لحساب قناع الشبكة نطبق المعادلة الحسابية التالية", start_seconds=120.0, duration_seconds=20.0, end_seconds=140.0),
    ]

    visuals = extract_visual_observations_from_lesson(
        video_id="test_vid_123",
        segments=segments,
        title="محاضرة الشبكات",
    )

    categories = {v.category for v in visuals}
    assert VisualCategory.SLIDE in categories  # Intro slide
    assert VisualCategory.DIAGRAM in categories
    assert VisualCategory.CODE_SNIPPET in categories
    assert VisualCategory.EQUATION in categories

    diagram_obs = next(v for v in visuals if v.category == VisualCategory.DIAGRAM)
    assert diagram_obs.timestamp_seconds == 15.0


# ── 5. Full Pipeline Lifecycle & Acceptance Scenario (Computer Networks) ───────

def test_full_video_learning_pipeline_acceptance_scenario(video_db):
    """End-to-end acceptance scenario: Computer Networks lecture covering TCP/UDP, Subnet Mask, and Routing Table."""
    db, student, other_student, subject = video_db

    link = YouTubeLink(
        id=uuid.uuid4(),
        subject_id=subject.id,
        owner_id=student.id,
        video_id="abcNetwork1",
        url="https://www.youtube.com/watch?v=abcNetwork1",
        title="Computer Networks Lecture 1: TCP/UDP & Subnetting",
        processing_status="pending",
    )
    db.add(link)
    db.commit()

    mock_transcript = [
        TimestampedTranscriptSegment(text="أهلاً بكم في محاضرة شبكات الحاسب، وسنشرح اليوم بروتوكول TCP وبروتوكول UDP.", start_seconds=0.0, duration_seconds=40.0, end_seconds=40.0),
        TimestampedTranscriptSegment(text="مخطط توضيحي للمقارنة بين موثوقية TCP وسرعة UDP.", start_seconds=45.0, duration_seconds=40.0, end_seconds=85.0),
        TimestampedTranscriptSegment(text="والآن ننتقل إلى قناع الشبكة Subnet Mask وكيف نحدد معرف الشبكة ومعرف الأجهزة.", start_seconds=90.0, duration_seconds=50.0, end_seconds=140.0),
        TimestampedTranscriptSegment(text="كما نستعرض جدول التوجيه Routing Table في الراوتر لتوجيه حزم البيانات.", start_seconds=150.0, duration_seconds=50.0, end_seconds=200.0),
    ]

    with patch("app.services.video_learning.pipeline.fetch_timestamped_transcript", return_value=(mock_transcript, "ar")), \
         patch("app.services.video_learning.pipeline.fetch_video_metadata", return_value=VideoMetadata(
             video_id="abcNetwork1",
             url="https://www.youtube.com/watch?v=abcNetwork1",
             title="Computer Networks Lecture 1: TCP/UDP & Subnetting",
             channel_name="Dr. Networks Academy",
             duration_seconds=200,
         )), \
         patch("app.services.storage.neon_storage.upload_file", return_value="neon-key"):
        result = process_video_learning(db=db, youtube_link_id=link.id)

    assert result.status == VideoProcessingState.READY
    assert result.has_captions is True
    assert result.duration_seconds == 200
    assert result.channel_name == "Dr. Networks Academy"
    assert result.concepts_count >= 3
    assert result.markdown_storage_key is not None

    # Verify DB persistence
    db.refresh(link)
    assert link.processing_status == "ready"
    assert link.visual_analysis_status == "ready"

    # Verify timestamped chunks created
    chunks = db.scalars(select(YouTubeChunk).where(YouTubeChunk.youtube_link_id == link.id)).all()
    assert len(chunks) > 0
    first_chunk = chunks[0]
    assert first_chunk.start_seconds == 0.0
    assert first_chunk.end_seconds > 0.0

    # Verify concepts registered in DB
    concepts = db.scalars(select(ExtractedConcept).where(ExtractedConcept.subject_id == subject.id)).all()
    concept_names = {c.name for c in concepts}
    assert "TCP" in concept_names
    assert "UDP" in concept_names
    assert "Subnet Mask" in concept_names

    # Verify relationship between TCP and UDP registered
    rels = db.scalars(select(ConceptRelationship).where(ConceptRelationship.subject_id == subject.id)).all()
    assert len(rels) >= 1
    assert any(r.relationship_type == "compares_with" for r in rels)


def test_video_without_captions_handling(video_db):
    """Verify that a video without transcripts gracefully marks no_captions without crashing."""
    db, student, other_student, subject = video_db

    link = YouTubeLink(
        id=uuid.uuid4(),
        subject_id=subject.id,
        owner_id=student.id,
        video_id="noCaptions1",
        url="https://www.youtube.com/watch?v=noCaptions1",
        title="Silent or Restricted Video",
        processing_status="pending",
    )
    db.add(link)
    db.commit()

    with patch("app.services.video_learning.pipeline.fetch_timestamped_transcript", return_value=None), \
         patch("app.services.video_learning.pipeline.fetch_video_metadata", return_value=VideoMetadata(
             video_id="noCaptions1",
             url="https://www.youtube.com/watch?v=noCaptions1",
             title="Silent Video",
         )):
        result = process_video_learning(db=db, youtube_link_id=link.id)

    assert result.status == VideoProcessingState.NO_CAPTIONS
    assert result.has_captions is False
    db.refresh(link)
    assert link.processing_status == "no_captions"


# ── 6. RAG Retrieval with Timestamps ──────────────────────────────────────────

def test_rag_retrieval_includes_timestamps_and_urls(video_db):
    """Verify that retrieve_for_subject returns exact timestamps and clickable video URLs."""
    db, student, other_student, subject = video_db

    link = YouTubeLink(
        id=uuid.uuid4(),
        subject_id=subject.id,
        owner_id=student.id,
        video_id="ytRAGtest01",
        url="https://www.youtube.com/watch?v=ytRAGtest01",
        title="Routing and Switching Tutorial",
        processing_status="ready",
    )
    chunk = YouTubeChunk(
        id=uuid.uuid4(),
        youtube_link_id=link.id,
        chunk_index=1,
        content="[08:35] Routing Table: The router checks the routing table to forward packets to the destination subnet.",
        start_seconds=515.0,
        end_seconds=575.0,
        segment_title="Routing Table Forwarding",
        visual_description="[مخطط: Routing Table]",
    )
    db.add_all([link, chunk])
    db.commit()

    passages = retrieve_for_subject(db, subject_id=subject.id, query="routing table subnet packets")
    assert len(passages) >= 1
    top = passages[0]
    assert "YouTube:" in top.file_name
    assert top.start_seconds == 515.0
    assert top.timestamp_url == "https://www.youtube.com/watch?v=ytRAGtest01&t=515s"
    assert top.visual_description == "[مخطط: Routing Table]"


# ── 7. AI Study Agent ToolRegistry Integration ────────────────────────────────

def test_study_agent_video_tools(video_db):
    """Test AI Study Agent tools: search_video_knowledge, get_video_segment, and compare_video_with_resources."""
    db, student, other_student, subject = video_db

    # Create video with chunk
    link = YouTubeLink(
        id=uuid.uuid4(),
        subject_id=subject.id,
        owner_id=student.id,
        video_id="compareVid1",
        url="https://www.youtube.com/watch?v=compareVid1",
        title="TCP Protocol Deep Dive",
        processing_status="ready",
    )
    chunk = YouTubeChunk(
        id=uuid.uuid4(),
        youtube_link_id=link.id,
        chunk_index=1,
        content="[05:10] The instructor explains TCP three way handshake: SYN, SYN-ACK, ACK.",
        start_seconds=310.0,
        end_seconds=380.0,
        segment_title="Three Way Handshake",
    )

    # Create uploaded textbook resource
    res = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="Computer_Networking_Textbook.pdf",
        mime_type="application/pdf",
        size_bytes=1000,
        sha256="sha-pdf",
        secure_url="neon://bucket/pdf",
        processing_status="ready",
    )
    res_chunk = ResourceChunk(
        id=uuid.uuid4(),
        resource_id=res.id,
        chunk_index=1,
        page_number=45,
        content="TCP establishes a reliable connection using the three way handshake mechanism.",
    )
    db.add_all([link, chunk, res, res_chunk])
    db.commit()

    registry = ToolRegistry(db=db, student_id=student.id, subject_id=subject.id)

    # 1. Search video knowledge tool
    search_res = registry.execute_tool("search_video_knowledge", {"query": "handshake TCP"})
    assert search_res.success is True
    assert search_res.result["matches_count"] >= 1
    assert "https://www.youtube.com/watch?v=compareVid1&t=310s" in str(search_res.result)

    # 2. Get specific segment by timestamp (second 320 is in [310, 380])
    seg_res = registry.execute_tool("get_video_segment", {"video_id": "compareVid1", "timestamp_seconds": 320.0})
    assert seg_res.success is True
    assert seg_res.result["found"] is True
    assert seg_res.result["start_seconds"] == 310.0

    # 3. Compare video with course textbook
    comp_res = registry.execute_tool("compare_video_with_resources", {"video_id": "compareVid1", "query": "handshake"})
    assert comp_res.success is True
    assert comp_res.result["video_passages_count"] >= 1
    assert comp_res.result["document_passages_count"] >= 1


def test_video_tool_tenant_isolation(video_db):
    """Verify that a student who is not a member of the subject is blocked with TenantAccessDenied."""
    db, student, other_student, subject = video_db

    # other_student is NOT a member of subject
    with pytest.raises(TenantAccessDenied):
        ToolRegistry(db=db, student_id=other_student.id, subject_id=subject.id)
