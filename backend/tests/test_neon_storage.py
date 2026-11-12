from __future__ import annotations

import io
from collections.abc import Generator
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import Resource, ResourceChunk, Subject, SubjectMembership, UserProfile
from app.db.session import get_db
from app.main import app
from app.services.retrieval import retrieve_for_subject
from app.services.storage import neon_storage


@pytest.fixture
def client_and_db() -> Generator[tuple[TestClient, Session, UserProfile, Subject], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    db.add_all([student, admin])
    db.flush()
    subject = Subject(name="Operating Systems", created_by=admin.id)
    db.add(subject)
    db.flush()
    db.add(SubjectMembership(user_id=student.id, subject_id=subject.id))
    db.commit()

    def override_db() -> Generator[Session, None, None]:
        with factory() as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_profile] = lambda: student
    try:
        yield TestClient(app), db, student, subject
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


# --- Unit Tests: Object Key & Path Traversal Security ---

def test_sanitize_filename_prevents_path_traversal() -> None:
    assert neon_storage.sanitize_filename("../../etc/passwd") == "passwd"
    assert neon_storage.sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert neon_storage.sanitize_filename("subfolder/my-file.pdf") == "my-file.pdf"
    assert neon_storage.sanitize_filename("   ") == "document.bin"
    assert neon_storage.sanitize_filename("..") == "document.bin"
    assert neon_storage.sanitize_filename("\x00important.pdf") == "important.pdf"


def test_build_object_key_format() -> None:
    user_id = uuid4()
    doc_id = uuid4()
    key = neon_storage.build_object_key(user_id=user_id, document_id=doc_id, filename="lecture.pdf")
    assert key == f"users/{user_id}/documents/{doc_id}/lecture.pdf"
    assert not key.startswith("/")
    assert ".." not in key


# --- Unit Tests: Storage Service CRUD & Presigned URLs ---

def test_storage_crud_and_presigned_url(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_s3 = MagicMock()
    mock_s3.upload_fileobj.return_value = None
    mock_s3.generate_presigned_url.return_value = "https://s3.neon.tech/ai-documents/users/1/lecture.pdf?sig=test"

    def mock_download_fileobj(Bucket, Key, Fileobj):
        Fileobj.write(b"mocked neon binary content")

    mock_s3.download_fileobj.side_effect = mock_download_fileobj
    mock_s3.head_object.return_value = {"ContentLength": 26}
    mock_s3.delete_object.return_value = {}
    mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "users/1/doc.pdf"}]}

    monkeypatch.setattr(neon_storage, "get_s3_client", lambda: mock_s3)

    # 1. Upload
    result = neon_storage.upload_file(b"test content", "users/1/test.pdf", bucket="ai-documents")
    assert result["bucket"] == "ai-documents"
    assert result["key"] == "users/1/test.pdf"
    assert result["storage_provider"] == "neon"
    mock_s3.upload_fileobj.assert_called_once()

    # 2. Download
    content = neon_storage.download_file("users/1/test.pdf", bucket="ai-documents")
    assert content == b"mocked neon binary content"

    # 3. Exists
    assert neon_storage.file_exists("users/1/test.pdf", bucket="ai-documents") is True

    # 4. Presigned URL
    url = neon_storage.generate_presigned_url("users/1/test.pdf", bucket="ai-documents", filename="my-download.pdf")
    assert "https://s3.neon.tech" in url

    # 5. List
    keys = neon_storage.list_files("users/1/", bucket="ai-documents")
    assert keys == ["users/1/doc.pdf"]

    # 6. Delete
    deleted = neon_storage.delete_file("users/1/test.pdf", bucket="ai-documents")
    assert deleted is True
    mock_s3.delete_object.assert_called_once()


# --- Integration Tests: Upload, RAG Pipeline & Database Verification ---

def test_direct_upload_creates_neon_record_and_chunks(
    client_and_db: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db, student, subject = client_and_db

    uploaded_keys = []

    def mock_upload(content, key, **kwargs):
        uploaded_keys.append(key)
        return {"bucket": "ai-documents", "key": key, "storage_provider": "neon"}

    monkeypatch.setattr(neon_storage, "upload_file", mock_upload)

    file_content = b"Operating Systems Lecture 1. Processes and Threads are fundamental concepts. A process is an executing program instance."
    response = client.post(
        f"/api/v1/subjects/{subject.id}/resources/upload-direct",
        files={"file": ("os_lecture.txt", io.BytesIO(file_content), "text/plain")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["file_name"] == "os_lecture.txt"
    assert data["storage_provider"] == "neon"
    assert len(uploaded_keys) == 1

    # Verify Database Record
    res_id = UUID(data["id"])
    db_res = db.scalar(select(Resource).where(Resource.id == res_id))
    assert db_res is not None
    assert db_res.storage_provider == "neon"
    assert db_res.storage_key is not None
    assert db_res.storage_bucket == "ai-documents"

    # Verify RAG Chunks created
    chunks = list(db.scalars(select(ResourceChunk).where(ResourceChunk.resource_id == res_id)).all())
    assert len(chunks) > 0
    assert "Processes and Threads" in chunks[0].content

    # Test RAG Retrieval for this document
    passages = retrieve_for_subject(db, subject_id=subject.id, query="What is a process and thread?")
    assert len(passages) > 0
    assert passages[0].resource_id == res_id
    assert "Processes and Threads" in passages[0].content


def test_download_returns_neon_presigned_url(
    client_and_db: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db, student, subject = client_and_db

    monkeypatch.setattr(
        neon_storage,
        "generate_presigned_url",
        lambda key, **kwargs: f"https://s3.us-east-2.neon.tech/ai-documents/{key}?token=presigned123",
    )

    # Insert resource with storage_provider='neon'
    res = Resource(
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="algorithms.pdf",
        mime_type="application/pdf",
        size_bytes=500,
        sha256="abc1234567890",
        storage_provider="neon",
        storage_bucket="ai-documents",
        storage_key="subjects/123/algorithms.pdf",
        secure_url="neon://ai-documents/subjects/123/algorithms.pdf",
        processing_status="ready",
    )
    db.add(res)
    db.commit()

    resp = client.get(f"/api/v1/subjects/{subject.id}/resources/{res.id}/download")
    assert resp.status_code == 200
    assert "https://s3.us-east-2.neon.tech" in resp.json()["download_url"]
    assert "token=presigned123" in resp.json()["download_url"]


def test_delete_resource_cleans_up_neon_object_and_chunks(
    client_and_db: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db, student, subject = client_and_db

    deleted_keys = []
    monkeypatch.setattr(neon_storage, "delete_file", lambda key, **kwargs: deleted_keys.append(key))

    res = Resource(
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="notes.pdf",
        mime_type="application/pdf",
        size_bytes=200,
        sha256="unique_notes_sha",
        storage_provider="neon",
        storage_bucket="ai-documents",
        storage_key="subjects/123/notes.pdf",
        secure_url="neon://ai-documents/subjects/123/notes.pdf",
        processing_status="ready",
    )
    db.add(res)
    db.flush()
    db.add(ResourceChunk(resource_id=res.id, chunk_index=0, content="Sample chunk content"))
    db.commit()

    # Perform DELETE
    resp = client.delete(f"/api/v1/subjects/{subject.id}/resources/{res.id}")
    assert resp.status_code == 204

    # Verify S3 cleanup
    assert "subjects/123/notes.pdf" in deleted_keys

    # Verify DB cleanup
    assert db.scalar(select(Resource).where(Resource.id == res.id)) is None
    assert db.scalar(select(ResourceChunk).where(ResourceChunk.resource_id == res.id)) is None


def test_security_outsider_cannot_access_or_download_resource(
    client_and_db: tuple[TestClient, Session, UserProfile, Subject]
) -> None:
    client, db, student, subject = client_and_db

    res = Resource(
        subject_id=subject.id,
        uploaded_by=student.id,
        file_name="private_exam.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        sha256="exam_sha_private",
        storage_provider="neon",
        storage_bucket="ai-documents",
        storage_key="subjects/123/exam.pdf",
        secure_url="neon://ai-documents/subjects/123/exam.pdf",
        processing_status="ready",
    )
    db.add(res)
    db.commit()

    # Switch identity to outsider without membership
    outsider = UserProfile(id=uuid4(), email="outsider@example.test", role="student")
    app.dependency_overrides[get_current_profile] = lambda: outsider

    # Download attempt
    resp = client.get(f"/api/v1/subjects/{subject.id}/resources/{res.id}/download")
    assert resp.status_code == 404

    # Delete attempt
    del_resp = client.delete(f"/api/v1/subjects/{subject.id}/resources/{res.id}")
    assert del_resp.status_code == 404


def test_health_endpoints(client_and_db: tuple[TestClient, Session, UserProfile, Subject]) -> None:
    client, _, _, _ = client_and_db

    res_live = client.get("/health/live")
    assert res_live.status_code == 200
    assert res_live.json() == {"status": "ok"}

    res_health = client.get("/health")
    assert res_health.status_code == 200
    data = res_health.json()
    assert data["status"] == "ok"
    assert "checks" in data
    assert "storage" in data["checks"]
    assert "database" in data["checks"]
    assert "ai_provider" in data["checks"]
