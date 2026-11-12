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
    KnowledgeProcessingJob,
    Resource,
    Subject,
    SubjectMembership,
    UploadBatch,
    UserProfile,
)
from app.services.knowledge_ingestion.pipeline import run_knowledge_ingestion_pipeline
from app.services.knowledge_ingestion.batch_processor import (
    MAX_BATCH_FILES,
    create_upload_batch,
    natural_sort_key,
    process_batch_upload,
    retry_failed_resource,
    synthesize_sequential_images_markdown,
)


@pytest.fixture
def batch_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()

    student = UserProfile(id=uuid.uuid4(), email="student@batch.test", role="student", skill_level=5)
    subject = Subject(id=uuid.uuid4(), name="شبكات الحاسب المتقدمة", created_by=student.id)
    membership = SubjectMembership(user_id=student.id, subject_id=subject.id, role="student")
    session.add_all([student, subject, membership])
    session.commit()

    try:
        yield session, student, subject
    finally:
        session.close()


def _make_dummy_pdf(text: str) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": text})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_dummy_docx(text: str) -> bytes:
    doc = DocxDocument()
    doc.add_heading("الفصل الأول", level=1)
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_natural_sort_key():
    """Verify that file names with numbers sort naturally (1, 2, 10)."""
    files = ["page_10.png", "page_1.png", "page_2.png", "page_20.png"]
    sorted_files = sorted(files, key=natural_sort_key)
    assert sorted_files == ["page_1.png", "page_2.png", "page_10.png", "page_20.png"]


def test_multi_pdf_batch_upload(batch_db):
    """Test batch upload with multiple PDFs processed independently."""
    db, student, subject = batch_db

    pdf1_bytes = _make_dummy_pdf("Chapter 1: OSI Model")
    pdf2_bytes = _make_dummy_pdf("Chapter 2: TCP/IP Stack")

    batch = create_upload_batch(
        db=db,
        subject_id=subject.id,
        student_id=student.id,
        title="دفعة الفصول الأولى",
        total_files=2,
    )
    assert batch.status == "pending"
    assert batch.total_files == 2

    files_data = [
        {"file_name": "chapter_1.pdf", "content": pdf1_bytes, "mime_type": "application/pdf"},
        {"file_name": "chapter_2.pdf", "content": pdf2_bytes, "mime_type": "application/pdf"},
    ]

    with patch("app.services.storage.neon_storage.upload_file", return_value="neon-key"):
        result = process_batch_upload(
            db=db,
            batch_id=batch.id,
            subject_id=subject.id,
            uploaded_by=student.id,
            files_data=files_data,
        )

    assert result["status"] == "completed"
    assert result["success_count"] == 2
    assert result["failed_count"] == 0
    assert len(result["resources"]) == 2

    # Verify database persistence
    refreshed_batch = db.get(UploadBatch, batch.id)
    assert refreshed_batch.status == "completed"
    assert refreshed_batch.success_count == 2

    resources = db.scalars(select(Resource).where(Resource.batch_id == batch.id)).all()
    assert len(resources) == 2
    assert {r.file_name for r in resources} == {"chapter_1.pdf", "chapter_2.pdf"}


def test_multi_image_synthesis(batch_db):
    """Test sequential images synthesized into a unified markdown document with source references."""
    db, student, subject = batch_db

    img1_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    img2_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR2"
    img3_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR3"

    batch = create_upload_batch(
        db=db,
        subject_id=subject.id,
        student_id=student.id,
        title="لوحات المحاضرة الأولى",
        total_files=3,
    )

    files_data = [
        {"file_name": "board_page_2.png", "content": img2_bytes, "mime_type": "image/png"},
        {"file_name": "board_page_1.png", "content": img1_bytes, "mime_type": "image/png"},
        {"file_name": "board_page_10.png", "content": img3_bytes, "mime_type": "image/png"},
    ]

    uploaded_calls = []

    def mock_upload(content, key, bucket, content_type):
        uploaded_calls.append({"key": key, "content": content, "type": content_type})
        return key

    with patch("app.services.storage.neon_storage.upload_file", side_effect=mock_upload):
        result = process_batch_upload(
            db=db,
            batch_id=batch.id,
            subject_id=subject.id,
            uploaded_by=student.id,
            files_data=files_data,
        )

    assert result["status"] == "completed"
    assert result["image_synthesis"] is not None
    assert result["image_synthesis"]["images_count"] == 3
    # Check natural sort order in synthesis
    assert result["image_synthesis"]["ordered_filenames"] == [
        "board_page_1.png",
        "board_page_2.png",
        "board_page_10.png",
    ]

    # Verify synthesized markdown was uploaded to Neon storage
    synth_uploads = [u for u in uploaded_calls if "synthesized_images.md" in u["key"]]
    assert len(synth_uploads) == 1
    synth_md = synth_uploads[0]["content"].decode("utf-8")
    assert "*مرجع الصورة الأصلية: board_page_1.png*" in synth_md
    assert "*مرجع الصورة الأصلية: board_page_2.png*" in synth_md
    assert "*مرجع الصورة الأصلية: board_page_10.png*" in synth_md


def test_mixed_format_batch(batch_db):
    """Test mixed batch with PDF, DOCX, and PNG."""
    db, student, subject = batch_db

    pdf_bytes = _make_dummy_pdf("Computer Networks PDF")
    docx_bytes = _make_dummy_docx("Computer Networks DOCX summary")
    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

    batch = create_upload_batch(
        db=db,
        subject_id=subject.id,
        student_id=student.id,
        title="دفعة مختلطة",
        total_files=3,
    )

    files_data = [
        {"file_name": "lecture1.pdf", "content": pdf_bytes, "mime_type": "application/pdf"},
        {"file_name": "summary.docx", "content": docx_bytes, "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        {"file_name": "diagram.png", "content": img_bytes, "mime_type": "image/png"},
    ]

    with patch("app.services.storage.neon_storage.upload_file", return_value="neon-key"):
        result = process_batch_upload(
            db=db,
            batch_id=batch.id,
            subject_id=subject.id,
            uploaded_by=student.id,
            files_data=files_data,
        )

    assert result["status"] == "completed"
    assert result["success_count"] == 3
    assert result["failed_count"] == 0


def test_batch_partial_failure_preserves_successful_files(batch_db):
    """Verify that a failure on one file does NOT discard or rollback successful files."""
    db, student, subject = batch_db

    pdf_bytes = _make_dummy_pdf("Valid PDF document")
    corrupt_bytes = b"NOT_A_VALID_DOCUMENT_BINARY_CRASH"

    batch = create_upload_batch(
        db=db,
        subject_id=subject.id,
        student_id=student.id,
        title="دفعة تجريبية",
        total_files=2,
    )

    files_data = [
        {"file_name": "valid_ch1.pdf", "content": pdf_bytes, "mime_type": "application/pdf"},
        {"file_name": "corrupt_ch2.pdf", "content": corrupt_bytes, "mime_type": "application/pdf"},
    ]

    original_run = run_knowledge_ingestion_pipeline

    def mock_pipeline(*, db, resource_id, content_bytes=None):
        res = db.get(Resource, resource_id)
        if "corrupt" in res.file_name:
            raise RuntimeError("Corrupted PDF stream cannot be parsed")
        return original_run(db=db, resource_id=resource_id, content_bytes=content_bytes)

    with patch("app.services.storage.neon_storage.upload_file", return_value="neon-key"), \
         patch("app.services.knowledge_ingestion.batch_processor.run_knowledge_ingestion_pipeline", side_effect=mock_pipeline):
        result = process_batch_upload(
            db=db,
            batch_id=batch.id,
            subject_id=subject.id,
            uploaded_by=student.id,
            files_data=files_data,
        )

    assert result["status"] == "partially_completed"
    assert result["success_count"] == 1
    assert result["failed_count"] == 1

    # Ensure successful resource is ready and intact in DB
    valid_res = db.scalar(select(Resource).where(Resource.file_name == "valid_ch1.pdf"))
    assert valid_res is not None
    assert valid_res.ingestion_status in {"ready", "completed"}

    # Ensure failed resource is marked failed
    corrupt_res = db.scalar(select(Resource).where(Resource.file_name == "corrupt_ch2.pdf"))
    assert corrupt_res is not None
    assert corrupt_res.ingestion_status == "failed"


def test_retry_failed_resource_updates_batch(batch_db):
    """Verify that retrying a failed file succeeds and updates batch status without re-running successful files."""
    db, student, subject = batch_db

    batch = create_upload_batch(
        db=db,
        subject_id=subject.id,
        student_id=student.id,
        title="دفعة قابلة للإعادة",
        total_files=2,
    )

    pdf_bytes = _make_dummy_pdf("Valid PDF document content")

    # Resource 1: Succeeded
    res1 = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=student.id,
        batch_id=batch.id,
        file_name="res1.pdf",
        mime_type="application/pdf",
        size_bytes=len(pdf_bytes),
        sha256="sha-1",
        secure_url="neon://b/k1",
        storage_key="k1",
        ingestion_status="ready",
        processing_status="ready",
    )
    # Resource 2: Failed initially
    res2 = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=student.id,
        batch_id=batch.id,
        file_name="res2.pdf",
        mime_type="application/pdf",
        size_bytes=len(pdf_bytes),
        sha256="sha-2",
        secure_url="neon://b/k2",
        storage_key="k2",
        ingestion_status="failed",
        processing_status="failed",
    )
    db.add_all([res1, res2])
    batch.success_count = 1
    batch.failed_count = 1
    batch.status = "partially_completed"
    db.commit()

    with patch("app.services.storage.neon_storage.download_file", return_value=pdf_bytes), \
         patch("app.services.storage.neon_storage.upload_file", return_value="neon-md-key"):
        retry_failed_resource(db=db, resource_id=res2.id)

    db.refresh(res2)
    assert res2.ingestion_status in {"ready", "completed"}

    db.refresh(batch)
    assert batch.status == "completed"
    assert batch.success_count == 2
    assert batch.failed_count == 0


def test_batch_limits_enforced(batch_db):
    """Verify that exceeding file limit (25) raises a validation error."""
    db, student, subject = batch_db

    batch = create_upload_batch(
        db=db,
        subject_id=subject.id,
        student_id=student.id,
        title="دفعة فائضة",
        total_files=30,
    )

    files_data = [
        {"file_name": f"file_{i}.pdf", "content": b"dummy", "mime_type": "application/pdf"}
        for i in range(MAX_BATCH_FILES + 1)
    ]

    with pytest.raises(ValueError, match="exceeding limit"):
        process_batch_upload(
            db=db,
            batch_id=batch.id,
            subject_id=subject.id,
            uploaded_by=student.id,
            files_data=files_data,
        )


def test_api_upload_batch_and_get_status(batch_db):
    """Test full HTTP endpoints for batch upload and status retrieval."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.auth import get_current_profile
    from app.db.session import get_db

    db, student, subject = batch_db

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_profile] = lambda: student
    client = TestClient(app)

    try:
        pdf_bytes = _make_dummy_pdf("Network Architectures Chapter 1")
        img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

        files = [
            ("files", ("network_intro.pdf", io.BytesIO(pdf_bytes), "application/pdf")),
            ("files", ("topology.png", io.BytesIO(img_bytes), "image/png")),
        ]

        with patch("app.services.storage.neon_storage.upload_file", return_value="neon-key"):
            res = client.post(
                f"/api/v1/subjects/{subject.id}/resources/upload-batch",
                data={"batch_title": "مقدمة شبكات الحاسب"},
                files=files,
            )

        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "مقدمة شبكات الحاسب"
        assert data["total_files"] == 2
        assert data["success_count"] == 2
        assert data["status"] == "completed"
        batch_id = data["batch_id"]

        # Now test GET /upload-batches/{batch_id}
        status_res = client.get(f"/api/v1/subjects/{subject.id}/upload-batches/{batch_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["id"] == batch_id
        assert status_data["status"] == "completed"
        assert len(status_data["resources"]) == 2

        # Test POST /{resource_id}/retry
        res_id = data["resources"][0]["resource_id"]
        with patch("app.services.storage.neon_storage.download_file", return_value=pdf_bytes), \
             patch("app.services.storage.neon_storage.upload_file", return_value="neon-key"):
            retry_res = client.post(f"/api/v1/subjects/{subject.id}/resources/{res_id}/retry")
        assert retry_res.status_code == 200
        retry_data = retry_res.json()
        assert retry_data["status"] == "ready"
        assert retry_data["resource_id"] == res_id

    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)

