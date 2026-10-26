from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import study_artifacts as artifact_route
from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import Resource, ResourceChunk, StudyArtifact, Subject, SubjectMembership, UserProfile
from app.db.session import get_db
from app.main import app
from app.services.gemini import GeneratedFlashcard, GeneratedFlashcardSet, GeminiRequestFailed


@pytest.fixture
def artifact_client() -> Generator[tuple[TestClient, sessionmaker[Session], UserProfile, Subject, Subject], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    student = UserProfile(id=uuid4(), role="student")
    admin = UserProfile(id=uuid4(), role="admin")
    with factory() as db:
        db.add_all([student, admin])
        db.flush()
        subject = Subject(name="Physics", created_by=admin.id)
        private_subject = Subject(name="Biology", created_by=admin.id)
        db.add_all([subject, private_subject])
        db.flush()
        db.add(SubjectMembership(user_id=student.id, subject_id=subject.id))
        resource = Resource(
            subject_id=subject.id,
            uploaded_by=student.id,
            file_name="physics.txt",
            mime_type="text/plain",
            size_bytes=20,
            sha256="a" * 64,
            cloudinary_public_id="study/physics.txt",
            secure_url="https://private.invalid/resource",
            processing_status="ready",
        )
        db.add(resource)
        db.flush()
        db.add(ResourceChunk(resource_id=resource.id, chunk_index=0, content="Force changes the motion of an object."))
        db.commit()
        db.refresh(subject)
        db.refresh(private_subject)

    def override_db() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_profile] = lambda: student
    try:
        yield TestClient(app), factory, student, subject, private_subject
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_flashcards_are_cached_and_subject_scoped(
    artifact_client: tuple[TestClient, Session, UserProfile, Subject, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _, subject, _ = artifact_client
    calls = 0

    def generate(passages):
        nonlocal calls
        calls += 1
        assert all("Force" in passage.content for passage in passages)
        return GeneratedFlashcardSet(
            title="الحركة والقوة",
            cards=[
                GeneratedFlashcard(front=f"بطاقة {index}?", back="القوة تغير حركة الجسم.", source_index=1)
                for index in range(1, 4)
            ],
        )

    monkeypatch.setattr(artifact_route, "generate_flashcard_draft", generate)

    first = client.post(f"/api/v1/subjects/{subject.id}/study-artifacts", json={"kind": "flashcards"})
    second = client.post(f"/api/v1/subjects/{subject.id}/study-artifacts", json={"kind": "flashcards"})
    listed = client.get(f"/api/v1/subjects/{subject.id}/study-artifacts?kind=flashcards")

    assert first.status_code == second.status_code == 201
    assert first.json()["content"]["cards"][0]["back"] == "القوة تغير حركة الجسم."
    assert second.json()["cached"] is True
    assert listed.status_code == 200 and len(listed.json()) == 1
    assert calls == 1
    with factory() as db:
        assert db.query(StudyArtifact).count() == 1


def test_nonmember_cannot_read_or_create_study_artifacts(
    artifact_client: tuple[TestClient, Session, UserProfile, Subject, Subject],
) -> None:
    client, _, _, _, private_subject = artifact_client

    assert client.get(f"/api/v1/subjects/{private_subject.id}/study-artifacts").status_code == 404
    assert client.post(
        f"/api/v1/subjects/{private_subject.id}/study-artifacts", json={"kind": "flashcards"}
    ).status_code == 404


def test_artifact_provider_failure_does_not_persist_fake_content(
    artifact_client: tuple[TestClient, Session, UserProfile, Subject, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _, subject, _ = artifact_client
    monkeypatch.setattr(artifact_route, "generate_flashcard_draft", lambda passages: (_ for _ in ()).throw(GeminiRequestFailed()))

    response = client.post(f"/api/v1/subjects/{subject.id}/study-artifacts", json={"kind": "flashcards"})

    assert response.status_code == 502
    with factory() as db:
        assert db.query(StudyArtifact).count() == 0


def test_study_artifact_kind_is_validated_and_extra_fields_are_rejected(
    artifact_client: tuple[TestClient, Session, UserProfile, Subject, Subject],
) -> None:
    client, _, _, subject, _ = artifact_client
    invalid_kind = client.post(f"/api/v1/subjects/{subject.id}/study-artifacts", json={"kind": "external_search"})
    extra = client.post(
        f"/api/v1/subjects/{subject.id}/study-artifacts",
        json={"kind": "flashcards", "subject_id": str(subject.id)},
    )

    assert invalid_kind.status_code == 422
    assert extra.status_code == 422
