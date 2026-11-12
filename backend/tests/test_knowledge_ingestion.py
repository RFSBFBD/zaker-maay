from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    AcademicChapter,
    AcademicTopic,
    ConceptRelationship,
    ExtractedConcept,
    KnowledgeProcessingJob,
    Resource,
    ResourceChunk,
    Subject,
    SubjectMembership,
    UserProfile,
)
from app.services.knowledge_ingestion.academic_organizer import (
    organize_subject_academic_hierarchy,
    register_document_chapter_and_topics,
)
from app.services.knowledge_ingestion.academic_understanding import analyze_academic_document
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
    IngestionState,
    RelationshipType,
)
from app.services.retrieval import retrieve_concept_and_prerequisites
from app.services.study_agent.agent import AIStudyAgent


@pytest.fixture
def ingestion_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()

    student = UserProfile(id=uuid.uuid4(), email="student@networks.test", role="student", skill_level=5)
    admin = UserProfile(id=uuid.uuid4(), email="admin@networks.test", role="admin")
    session.add_all([student, admin])
    session.flush()

    subject = Subject(id=uuid.uuid4(), name="Computer Networks", created_by=admin.id)
    session.add(subject)
    session.flush()

    membership = SubjectMembership(subject_id=subject.id, user_id=student.id)
    session.add(membership)
    session.commit()

    yield session, student, admin, subject

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ── 1. Format-Specific Extraction Tests ───────────────────────────────────────

def test_extract_docx_with_headings_and_tables():
    doc = DocxDocument()
    doc.add_heading("Network Layer Fundamentals", level=1)
    doc.add_paragraph("The network layer provides host-to-host communication services.")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Protocol"
    table.rows[0].cells[1].text = "Layer"
    table.rows[1].cells[0].text = "IP"
    table.rows[1].cells[1].text = "Network"

    buf = io.BytesIO()
    doc.save(buf)
    content = buf.getvalue()

    result = extract_document_content("network_layer.docx", content)
    assert result.extension == ".docx"
    assert len(result.pages) == 1
    page = result.pages[0]
    assert "Network Layer Fundamentals" in page.text
    assert len(page.tables) == 1
    assert page.tables[0][1][0] == "IP"


def test_extract_plain_text():
    raw = "# Chapter 1: Overview\nComputer networks interconnect autonomous computers."
    res = extract_document_content("ch1.txt", raw.encode("utf-8"))
    assert res.extension == ".txt"
    assert any("Overview" in h for h in res.pages[0].headings)
    assert "interconnect autonomous computers" in res.pages[0].text


# ── 2. Canonical Markdown Conversion Tests ────────────────────────────────────

def test_canonical_markdown_conversion():
    raw_text = (
        "Routing is defined as the process of selecting paths across a network.\n\n"
        "### Routing Algorithms\n"
        "Link state algorithms broadcast topology information to all nodes.\n"
        "Distance vector algorithms share routing tables with direct neighbors."
    )
    from app.services.knowledge_ingestion.schemas import (
        DocumentExtractionResult,
        ExtractedPageContent,
    )
    extracted = DocumentExtractionResult(
        file_name="Chapter 4 — Routing.pdf",
        extension=".pdf",
        total_pages_or_slides=1,
        pages=[
            ExtractedPageContent(
                page_or_slide_number=12,
                title="Routing Overview",
                text=raw_text,
                headings=["Routing Algorithms"],
            )
        ],
    )

    canonical = convert_to_canonical_markdown(
        resource_id=str(uuid.uuid4()),
        subject_id=str(uuid.uuid4()),
        file_name="Chapter 4 — Routing.pdf",
        extracted=extracted,
        subject_title="Computer Networks",
    )

    assert canonical.chapter_number == 4
    assert "# الفصل 4:" in canonical.markdown_content
    assert "## صفحة / شريحة 12" in canonical.markdown_content
    assert "### Routing Algorithms" in canonical.markdown_content
    assert "*مرجع المقطع: `Chapter 4 — Routing.pdf`, صفحة/شريحة 12*" in canonical.markdown_content


# ── 3. Academic Understanding & Concept Extraction ────────────────────────────

def test_academic_understanding_extracts_concepts_and_prerequisites():
    from app.services.knowledge_ingestion.schemas import CanonicalMarkdownDocument
    md_content = (
        "# الفصل 4: Routing\n\n"
        "> **المقرر**: Computer Networks\n\n"
        "## صفحة / شريحة 1\n\n"
        "Routing is defined as the process of finding paths between source and destination.\n\n"
        "### Distance Vector\n"
        "A distributed algorithm where nodes exchange distance estimates with neighbors.\n\n"
        "prerequisite: requires prior knowledge of IP Addressing."
    )
    doc = CanonicalMarkdownDocument(
        resource_id=str(uuid.uuid4()),
        subject_id=str(uuid.uuid4()),
        file_name="Chapter 4 — Routing.pdf",
        title="Routing",
        chapter_number=4,
        markdown_content=md_content,
        outline=["# الفصل 4: Routing", "### Distance Vector"],
    )

    understanding = analyze_academic_document(doc, subject_title="Computer Networks")
    assert understanding.detected_chapter_number == 4
    assert len(understanding.concepts) >= 1

    c_names = [c.name.lower() for c in understanding.concepts]
    assert any("routing" in name or "distance vector" in name for name in c_names)
    assert any("ip addressing" in p.lower() for p in understanding.prerequisites)


# ── 4. Acceptance Scenario: Random Upload Ordering & Missing Chapters ─────────

def test_acceptance_random_upload_ordering_and_gap_detection(ingestion_db):
    """Real-World Acceptance Test:
    Files uploaded in order: Chapter 4, Chapter 2, Chapter 3, Chapter 1.
    System organizes into 1, 2, 3, 4.
    If Chapter 3 is deleted, it detects Chapter 3 is missing without inventing content.
    """
    db, student, admin, subject = ingestion_db

    # Upload files in random order: 4, 2, 3, 1
    files_order = [
        ("Chapter 4 — Routing.pdf", 4, "Routing"),
        ("Chapter 2 — Network Models.pdf", 2, "Network Models"),
        ("Chapter 3 — IP Addressing.pdf", 3, "IP Addressing"),
        ("Chapter 1 — Introduction.pdf", 1, "Introduction"),
    ]

    resources = []
    for fn, ch_num, title in files_order:
        res = Resource(
            id=uuid.uuid4(),
            subject_id=subject.id,
            uploaded_by=student.id,
            file_name=fn,
            mime_type="application/pdf",
            size_bytes=1024,
            sha256=f"sha256_{fn}",
            academic_chapter=ch_num,
            chapter_title=title,
            secure_url=f"neon://ai-docs/{fn}",
            processing_status="ready",
            ingestion_status="ready",
        )
        db.add(res)
        resources.append(res)
    db.commit()

    # Organize chapters
    report = organize_subject_academic_hierarchy(db, subject.id)
    assert report.total_chapters_detected == 4
    ordered_numbers = [c["chapter_number"] for c in report.ordered_chapters]
    assert ordered_numbers == [1, 2, 3, 4]  # Verified logical order!
    assert report.detected_missing_chapters == []

    # Now simulate a gap: delete Chapter 3
    ch3_res = next(r for r in resources if r.academic_chapter == 3)
    db.delete(ch3_res)
    ch3_db = db.scalar(select(AcademicChapter).where(AcademicChapter.subject_id == subject.id, AcademicChapter.chapter_number == 3))
    if ch3_db:
        db.delete(ch3_db)
    db.commit()

    gap_report = organize_subject_academic_hierarchy(db, subject.id)
    assert gap_report.total_chapters_detected == 3
    assert gap_report.detected_missing_chapters == [3]  # Chapter 3 detected as missing!


# ── 5. Cross-Document Knowledge Graph & Contradiction Detection ────────────────

def test_cross_document_graph_and_contradiction_handling(ingestion_db):
    db, student, _, subject = ingestion_db

    res1 = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="book_a.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256="sha_book_a",
        academic_chapter=1,
        chapter_title="Book A",
        secure_url="neon://ai-docs/book_a.pdf",
        processing_status="ready",
    )
    res2 = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="book_b.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256="sha_book_b",
        academic_chapter=2,
        chapter_title="Book B",
        secure_url="neon://ai-docs/book_b.pdf",
        processing_status="ready",
    )
    db.add_all([res1, res2])
    db.commit()

    from app.services.knowledge_ingestion.schemas import (
        AcademicUnderstandingResult,
        ExtractedConceptItem,
    )

    # Document 1 defines "Bandwidth"
    und1 = AcademicUnderstandingResult(
        subject_title=subject.name,
        concepts=[
            ExtractedConceptItem(
                name="Bandwidth",
                definition="The maximum rate of data transfer across a given path measured in bits per second.",
                page_or_slide_number=5,
            )
        ],
        prerequisites=[],
    )
    ingest_concepts_and_build_relationships(
        db=db, subject_id=subject.id, resource_id=res1.id, understanding=und1
    )

    # Document 2 defines "Bandwidth" with a different phrasing / nuance (frequency width)
    und2 = AcademicUnderstandingResult(
        subject_title=subject.name,
        concepts=[
            ExtractedConceptItem(
                name="Bandwidth",
                definition="The width of the frequency range that a transmission signal occupies in Hertz.",
                page_or_slide_number=18,
            )
        ],
        prerequisites=["Bandwidth"],
    )
    ingest_concepts_and_build_relationships(
        db=db, subject_id=subject.id, resource_id=res2.id, understanding=und2
    )

    # Verify conflict record was preserved in database
    conflict_rel = db.scalar(
        select(ConceptRelationship).where(
            ConceptRelationship.subject_id == subject.id,
            ConceptRelationship.relationship_type == RelationshipType.POTENTIALLY_CONFLICTS_WITH.value,
        )
    )
    assert conflict_rel is not None
    assert "اختلاف في صياغة أو تفسير المفهوم" in conflict_rel.conflict_details
    assert "book_a.pdf" in conflict_rel.conflict_details
    assert "book_b.pdf" in conflict_rel.conflict_details


# ── 6. Full Pipeline Execution & Idempotency ──────────────────────────────────

def test_run_knowledge_ingestion_pipeline_idempotency(ingestion_db):
    db, student, _, subject = ingestion_db

    res = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="Chapter 4 — Routing.txt",
        mime_type="text/plain",
        size_bytes=512,
        sha256="sha_routing_txt",
        storage_key="test/routing.txt",
        secure_url="neon://ai-docs/routing.txt",
        processing_status="pending",
    )
    db.add(res)
    db.commit()

    raw_content = (
        "# Chapter 4: Routing\n\n"
        "Routing is defined as selecting paths across a network.\n"
        "### Distance Vector\n"
        "Distance vector algorithm sends routing tables to direct neighbors.\n"
    ).encode("utf-8")

    with patch("app.services.storage.neon_storage.upload_file", return_value={"bucket": "ai-docs", "key": "test.md"}):
        # First run
        result1 = run_knowledge_ingestion_pipeline(db=db, resource_id=res.id, content_bytes=raw_content)
        assert result1.status == IngestionState.READY
        assert result1.chunks_created >= 1
        assert result1.academic_chapter == 4

        # Verify job record
        job = db.scalar(select(KnowledgeProcessingJob).where(KnowledgeProcessingJob.resource_id == res.id))
        assert job is not None
        assert job.status == "ready"
        assert job.progress_pct == 100

        # Second run (reprocessing / retry): Must be idempotent, no duplicate chunks
        result2 = run_knowledge_ingestion_pipeline(db=db, resource_id=res.id, content_bytes=raw_content)
        assert result2.status == IngestionState.READY
        assert result2.chunks_created == result1.chunks_created


# ── 7. RAG Prerequisite Retrieval & AI Study Agent Integration ───────────────

def test_rag_retrieves_prerequisites_for_agent(ingestion_db):
    db, student, _, subject = ingestion_db

    # Concept 1: IP Addressing (Chapter 3)
    c_ip = ExtractedConcept(
        id=uuid.uuid4(),
        subject_id=subject.id,
        resource_id=uuid.uuid4(),
        name="IP Addressing",
        normalized_name="ip addressing",
        definition="Numerical label assigned to each device connected to a computer network.",
        page_or_slide_number=8,
    )
    # Concept 2: Routing (Chapter 4)
    c_routing = ExtractedConcept(
        id=uuid.uuid4(),
        subject_id=subject.id,
        resource_id=uuid.uuid4(),
        name="Routing",
        normalized_name="routing",
        definition="Process of selecting paths across a computer network to forward packets.",
        page_or_slide_number=2,
    )
    db.add_all([c_ip, c_routing])
    db.flush()

    # Link: IP Addressing is PREREQUISITE_OF Routing
    rel = ConceptRelationship(
        id=uuid.uuid4(),
        subject_id=subject.id,
        source_concept_id=c_ip.id,
        target_concept_id=c_routing.id,
        relationship_type=RelationshipType.PREREQUISITE_OF.value,
        description="IP Addressing is required before studying Routing.",
    )
    db.add(rel)
    db.commit()

    retrieved = retrieve_concept_and_prerequisites(db, subject_id=subject.id, query="Explain routing")
    assert len(retrieved["concepts"]) >= 1
    assert retrieved["concepts"][0]["name"] == "Routing"
    assert len(retrieved["prerequisites"]) >= 1
    assert retrieved["prerequisites"][0]["name"] == "IP Addressing"
    assert retrieved["prerequisites"][0]["required_for"] == "Routing"


def test_acceptance_agent_explains_routing_with_prerequisites_without_naming_files(ingestion_db):
    """Final Acceptance Scenario:
    Student asks: 'اشرح لي كيف يعمل الـ Routing من البداية والأساسيات'
    The Agent automatically:
    - Finds the routing chapter/concept.
    - Pulls prerequisite concepts (IP Addressing / Network Models) from earlier chapters.
    - Synthesizes the explanation without the student naming the files!
    """
    db, student, admin, subject = ingestion_db

    # Create Chapter 2 (Network Models) & Chapter 4 (Routing)
    res_ch2 = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="Chapter 2 — Network Models.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256="sha_ch2",
        academic_chapter=2,
        chapter_title="Network Models",
        secure_url="neon://ai-docs/ch2.pdf",
        processing_status="ready",
    )
    res_ch4 = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="Chapter 4 — Routing.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256="sha_ch4",
        academic_chapter=4,
        chapter_title="Routing",
        secure_url="neon://ai-docs/ch4.pdf",
        processing_status="ready",
    )
    db.add_all([res_ch2, res_ch4])
    db.flush()

    # Chunks
    db.add(
        ResourceChunk(
            resource_id=res_ch4.id,
            chunk_index=0,
            page_number=1,
            content="Routing determines path selection across routers using distance vector or link state algorithms.",
        )
    )
    db.add(
        ResourceChunk(
            resource_id=res_ch2.id,
            chunk_index=0,
            page_number=5,
            content="Network Layer delivers packets end-to-end based on logical addressing.",
        )
    )

    # Concept graph
    c_net = ExtractedConcept(
        id=uuid.uuid4(),
        subject_id=subject.id,
        resource_id=res_ch2.id,
        name="Network Layer",
        normalized_name="network layer",
        definition="The layer responsible for packet forwarding and host-to-host addressing.",
        page_or_slide_number=5,
    )
    c_rout = ExtractedConcept(
        id=uuid.uuid4(),
        subject_id=subject.id,
        resource_id=res_ch4.id,
        name="Routing",
        normalized_name="routing",
        definition="Selecting paths across a network to deliver packets from source to destination.",
        page_or_slide_number=1,
    )
    db.add_all([c_net, c_rout])
    db.flush()

    rel = ConceptRelationship(
        id=uuid.uuid4(),
        subject_id=subject.id,
        source_concept_id=c_net.id,
        target_concept_id=c_rout.id,
        relationship_type=RelationshipType.PREREQUISITE_OF.value,
        description="Network Layer foundations are required before studying Routing.",
    )
    db.add(rel)
    db.commit()

    agent = AIStudyAgent(db=db)

    # Student asks without naming any file or chapter
    user_query = "اشرح لي كيف يعمل الـ Routing من البداية والأساسيات"

    mock_answer = (
        "لشرح الـ Routing من البداية، نبدأ أولاً من الأساسيات في طبقة الشبكة (Network Layer) "
        "ثم ننتقل إلى آليات التوجيه واختيار المسارات في الفصل الرابع [S1]."
    )

    with patch("app.services.study_agent.agent.execute_llm_request_via_router", return_value=(mock_answer, "gemini-3.5-flash")):
        result = agent.process_message(
            student_id=student.id,
            subject_id=subject.id,
            message=user_query,
        )
        assert result.answer is not None
        assert "Routing" in result.answer or "طبقة الشبكة" in result.answer

        # Verify agent executed chapter hierarchy and prerequisite discovery tools
        tool_names = [t.tool_name for t in result.execution_trace.tools_executed]
        assert "get_subject_academic_chapters" in tool_names
        assert "get_concept_with_prerequisites" in tool_names

