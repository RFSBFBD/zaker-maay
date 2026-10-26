from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.youtube_links import parse_youtube_video_id
from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import Subject, SubjectMembership, UserProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client_and_users() -> Generator[tuple[TestClient, UserProfile, Subject, Subject], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    with factory() as session:
        session.add_all([student, admin])
        session.flush()
        subject = Subject(name="Physics", created_by=admin.id)
        private_subject = Subject(name="Biology", created_by=admin.id)
        session.add_all([subject, private_subject])
        session.flush()
        session.add(SubjectMembership(user_id=student.id, subject_id=subject.id))
        session.commit()
        session.refresh(subject)
        session.refresh(private_subject)

    def override_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), student, subject, private_subject
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def use_profile(profile: UserProfile) -> None:
    app.dependency_overrides[get_current_profile] = lambda: profile


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=abcdefghijk&t=20", "abcdefghijk"),
        ("https://youtu.be/abcdefghijk", "abcdefghijk"),
        ("https://youtube.com/shorts/abcdefghijk", "abcdefghijk"),
        ("https://m.youtube.com/embed/abcdefghijk", "abcdefghijk"),
        ("https://www.youtube.com/live/abcdefghijk", "abcdefghijk"),
    ],
)
def test_parse_youtube_video_id(url: str, video_id: str) -> None:
    assert parse_youtube_video_id(url) == video_id


@pytest.mark.parametrize(
    "url",
    [
        "http://youtube.com/watch?v=abcdefghijk",
        "https://youtube.com.attacker.example/watch?v=abcdefghijk",
        "https://youtube.com.evil/watch?v=abcdefghijk",
        "https://youtu.be/../../etc/passwd",
        "https://attacker.example/?url=https://youtube.com/watch?v=abcdefghijk",
        "https://user:pass@youtube.com/watch?v=abcdefghijk",
        "https://youtube.com:8443/watch?v=abcdefghijk",
        "https://youtube.com/watch?v=invalid",
    ],
)
def test_reject_unsafe_or_invalid_youtube_url(url: str) -> None:
    with pytest.raises(ValueError):
        parse_youtube_video_id(url)


def test_member_can_add_list_and_remove_video_link(client_and_users) -> None:
    client, student, subject, _ = client_and_users
    use_profile(student)

    created = client.post(
        f"/api/v1/subjects/{subject.id}/youtube-links",
        json={"url": "https://youtu.be/abcdefghijk"},
    )

    assert created.status_code == 201
    assert created.json()["video_id"] == "abcdefghijk"
    assert created.json()["url"] == "https://www.youtube.com/watch?v=abcdefghijk"
    assert client.get(f"/api/v1/subjects/{subject.id}/youtube-links").json()[0]["id"] == created.json()["id"]

    duplicate = client.post(
        f"/api/v1/subjects/{subject.id}/youtube-links",
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk"},
    )
    assert duplicate.status_code == 409

    removed = client.delete(f"/api/v1/subjects/{subject.id}/youtube-links/{created.json()['id']}")
    assert removed.status_code == 204
    assert client.get(f"/api/v1/subjects/{subject.id}/youtube-links").json() == []


def test_nonmember_cannot_add_or_list_video_links(client_and_users) -> None:
    client, student, _, private_subject = client_and_users
    use_profile(student)

    response = client.post(
        f"/api/v1/subjects/{private_subject.id}/youtube-links",
        json={"url": "https://youtu.be/abcdefghijk"},
    )

    assert response.status_code == 404
    assert client.get(f"/api/v1/subjects/{private_subject.id}/youtube-links").status_code == 404


def test_youtube_endpoint_rejects_unknown_payload_fields(client_and_users) -> None:
    client, student, subject, _ = client_and_users
    use_profile(student)

    response = client.post(
        f"/api/v1/subjects/{subject.id}/youtube-links",
        json={"url": "https://youtu.be/abcdefghijk", "owner_id": str(student.id)},
    )

    assert response.status_code == 422
