from collections.abc import Generator
import io
import wave
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
from app.services import cloudinary_storage
from app.services import gemini


@pytest.fixture
def resource_client() -> Generator[tuple[TestClient, Session, UserProfile, Subject], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    db.add_all([student, admin])
    db.flush()
    subject = Subject(name="Physics", created_by=admin.id)
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


def mock_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cloudinary_storage,
        "upload_private_asset",
        lambda content, *, public_id, resource_type: {
            "public_id": public_id,
            "secure_url": "https://private.invalid/asset",
        },
    )
    monkeypatch.setattr(cloudinary_storage, "delete_asset", lambda *, public_id, resource_type: None)


def one_second_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(1)
        audio.setframerate(8_000)
        audio.writeframes(bytes([128]) * 8_000)
    return output.getvalue()


def test_upload_stores_metadata_without_exposing_storage_url(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_storage(monkeypatch)
    client, db, student, subject = resource_client

    response = client.post(
        f"/api/v1/subjects/{subject.id}/resources",
        files={"file": ("lecture.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["file_name"] == "lecture.pdf"
    assert data["uploaded_by"] == str(student.id)
    assert data["sha256"]
    assert "secure_url" not in data
    stored = db.scalar(select(Resource).where(Resource.id == UUID(data["id"])))
    assert stored is not None and stored.secure_url == "https://private.invalid/asset"


def test_duplicate_upload_is_rejected_without_deleting_existing_asset(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_storage(monkeypatch)
    client, db, _, subject = resource_client
    path = f"/api/v1/subjects/{subject.id}/resources"
    file = {"file": ("lecture.pdf", b"%PDF-1.7\ncontent", "application/pdf")}

    first = client.post(path, files=file)
    duplicate = client.post(path, files=file)

    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_invalid_file_content_is_rejected_before_storage(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_upload(*args, **kwargs):
        pytest.fail("Storage must not be called for invalid files.")

    monkeypatch.setattr(cloudinary_storage, "upload_private_asset", unexpected_upload)
    client, _, _, subject = resource_client

    response = client.post(
        f"/api/v1/subjects/{subject.id}/resources",
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 415


def test_resource_endpoints_require_subject_membership(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_storage(monkeypatch)
    client, _, _, subject = resource_client
    uploaded = client.post(
        f"/api/v1/subjects/{subject.id}/resources",
        files={"file": ("lecture.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )
    outsider = UserProfile(id=uuid4(), role="student")
    app.dependency_overrides[get_current_profile] = lambda: outsider

    response = client.get(f"/api/v1/subjects/{subject.id}/resources")

    assert uploaded.status_code == 201
    assert response.status_code == 404


def test_download_returns_a_signed_link_only_after_membership_check(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_storage(monkeypatch)
    monkeypatch.setattr(
        cloudinary_storage, "create_download_url", lambda **kwargs: "https://signed.invalid/short-lived"
    )
    client, _, _, subject = resource_client
    uploaded = client.post(
        f"/api/v1/subjects/{subject.id}/resources",
        files={"file": ("lecture.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )
    resource_id = uploaded.json()["id"]

    response = client.get(f"/api/v1/subjects/{subject.id}/resources/{resource_id}/download")

    assert response.status_code == 200
    assert response.json() == {
        "download_url": "https://signed.invalid/short-lived",
        "expires_in_seconds": 600,
    }


def test_only_uploader_or_admin_can_delete_a_resource(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_storage(monkeypatch)
    client, db, _, subject = resource_client
    uploaded = client.post(
        f"/api/v1/subjects/{subject.id}/resources",
        files={"file": ("lecture.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )
    resource_id = uploaded.json()["id"]
    another_member = UserProfile(id=uuid4(), role="student")
    db.add(another_member)
    db.flush()
    db.add(SubjectMembership(user_id=another_member.id, subject_id=subject.id))
    db.commit()
    app.dependency_overrides[get_current_profile] = lambda: another_member

    denied = client.delete(f"/api/v1/subjects/{subject.id}/resources/{resource_id}")

    assert denied.status_code == 403


def test_audio_upload_is_not_sent_to_gemini_without_explicit_consent(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_storage(monkeypatch)

    def unexpected_transcription(*args, **kwargs):
        pytest.fail("Audio must not be sent to Gemini unless transcription was explicitly selected.")

    monkeypatch.setattr(gemini, "transcribe_audio", unexpected_transcription)
    client, _, _, subject = resource_client

    response = client.post(
        f"/api/v1/subjects/{subject.id}/resources",
        files={"file": ("lecture.wav", one_second_wav(), "audio/wav")},
    )

    assert response.status_code == 201
    assert response.json()["processing_status"] == "unsupported"
    assert response.json()["has_transcript"] is False


def test_audio_upload_transcribes_and_saves_only_after_explicit_consent(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_storage(monkeypatch)
    monkeypatch.setattr(
        gemini,
        "transcribe_audio",
        lambda content, mime_type: gemini.GeneratedTranscript(language="Arabic", transcript="هذا نص المحاضرة."),
    )
    client, db, _, subject = resource_client

    response = client.post(
        f"/api/v1/subjects/{subject.id}/resources",
        files={"file": ("lecture.wav", one_second_wav(), "audio/wav")},
        data={"transcribe_audio": "true"},
    )

    assert response.status_code == 201
    assert response.json()["processing_status"] == "ready"
    assert response.json()["transcript_language"] == "Arabic"
    assert response.json()["audio_duration_seconds"] == 1
    assert response.json()["has_transcript"] is True
    resource_id = UUID(response.json()["id"])
    resource = db.get(Resource, resource_id)
    assert resource is not None and resource.transcript_text == "هذا نص المحاضرة."
    assert db.scalar(select(ResourceChunk).where(ResourceChunk.resource_id == resource_id)).content == "هذا نص المحاضرة."

    transcript = client.get(f"/api/v1/subjects/{subject.id}/resources/{resource_id}/transcript")
    assert transcript.status_code == 200
    assert transcript.json()["timestamp_quality"] == "not_provided"


def test_transcription_provider_failure_leaves_audio_unstored_and_returns_error(
    resource_client: tuple[TestClient, Session, UserProfile, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db, _, subject = resource_client

    def failed_transcription(*args, **kwargs):
        raise gemini.GeminiRequestFailed

    def unexpected_upload(*args, **kwargs):
        pytest.fail("Storage must not be called after an opted-in transcription fails.")

    monkeypatch.setattr(gemini, "transcribe_audio", failed_transcription)
    monkeypatch.setattr(cloudinary_storage, "upload_private_asset", unexpected_upload)

    response = client.post(
        f"/api/v1/subjects/{subject.id}/resources",
        files={"file": ("lecture.wav", one_second_wav(), "audio/wav")},
        data={"transcribe_audio": "true"},
    )

    assert response.status_code == 502
    assert "بقي الملف على جهازك" in response.json()["detail"]
    assert db.query(Resource).count() == 0
