from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import StudySession, Subject, SubjectMembership, UserProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture
def session_client() -> Generator[tuple[TestClient, Session, UserProfile, Subject, Subject], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    db.add_all([student, admin])
    db.flush()
    physics = Subject(name="Physics", created_by=admin.id)
    biology = Subject(name="Biology", created_by=admin.id)
    db.add_all([physics, biology])
    db.flush()
    db.add(SubjectMembership(user_id=student.id, subject_id=physics.id))
    db.commit()

    def override_db() -> Generator[Session, None, None]:
        with factory() as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_profile] = lambda: student
    try:
        yield TestClient(app), db, student, physics, biology
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_session_uses_server_duration_and_rejects_concurrency(
    session_client: tuple[TestClient, Session, UserProfile, Subject, Subject],
) -> None:
    client, _, _, physics, biology = session_client

    started = client.post(
        "/api/v1/study-sessions",
        json={"subject_id": str(physics.id), "duration_minutes": 15},
    )
    concurrent = client.post(
        "/api/v1/study-sessions",
        json={"subject_id": str(physics.id), "duration_minutes": 15},
    )
    wrong_subject = client.post(
        "/api/v1/study-sessions",
        json={"subject_id": str(biology.id), "duration_minutes": 15},
    )

    assert started.status_code == 201
    assert started.json()["status"] == "active"
    assert 0 < started.json()["remaining_seconds"] <= 900
    assert concurrent.status_code == 409
    assert wrong_subject.status_code == 404
    restored = client.get("/api/v1/study-sessions/active")
    assert restored.status_code == 200
    assert restored.json()["id"] == started.json()["id"]


def test_client_cannot_choose_session_timestamps(
    session_client: tuple[TestClient, Session, UserProfile, Subject, Subject],
) -> None:
    client, _, _, physics, _ = session_client

    response = client.post(
        "/api/v1/study-sessions",
        json={
            "subject_id": str(physics.id),
            "duration_minutes": 15,
            "started_at": "2000-01-01T00:00:00Z",
            "planned_end_at": "2099-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 422


def test_expired_session_is_closed_using_server_time(
    session_client: tuple[TestClient, Session, UserProfile, Subject, Subject],
) -> None:
    client, db, student, physics, _ = session_client
    now = datetime.now(timezone.utc)
    expired = StudySession(
        user_id=student.id,
        subject_id=physics.id,
        started_at=now - timedelta(minutes=31),
        planned_end_at=now - timedelta(minutes=1),
    )
    db.add(expired)
    db.commit()

    response = client.get("/api/v1/study-sessions/active")
    db.refresh(expired)

    assert response.status_code == 200
    assert response.json() is None
    assert expired.status == "completed"
    assert expired.ended_at == expired.planned_end_at


def test_starting_after_expiry_closes_old_session_first(
    session_client: tuple[TestClient, Session, UserProfile, Subject, Subject],
) -> None:
    client, db, student, physics, _ = session_client
    now = datetime.now(timezone.utc)
    expired = StudySession(
        user_id=student.id,
        subject_id=physics.id,
        started_at=now - timedelta(minutes=31),
        planned_end_at=now - timedelta(minutes=1),
    )
    db.add(expired)
    db.commit()

    response = client.post(
        "/api/v1/study-sessions",
        json={"subject_id": str(physics.id), "duration_minutes": 10},
    )
    db.refresh(expired)

    assert response.status_code == 201
    assert expired.status == "completed"


def test_admin_cannot_open_a_student_study_session(
    session_client: tuple[TestClient, Session, UserProfile, Subject, Subject],
) -> None:
    client, _, _, physics, _ = session_client
    app.dependency_overrides[get_current_profile] = lambda: UserProfile(id=uuid4(), role="admin")

    response = client.post(
        "/api/v1/study-sessions",
        json={"subject_id": str(physics.id), "duration_minutes": 10},
    )

    assert response.status_code == 403


def test_ending_a_session_is_owner_scoped_and_finishes_it(
    session_client: tuple[TestClient, Session, UserProfile, Subject, Subject],
) -> None:
    client, db, student, physics, _ = session_client
    started = client.post(
        "/api/v1/study-sessions",
        json={"subject_id": str(physics.id), "duration_minutes": 15},
    )
    session_id = started.json()["id"]

    finished = client.post(f"/api/v1/study-sessions/{session_id}/end")
    missing = client.post(f"/api/v1/study-sessions/{uuid4()}/end")
    stored = db.scalar(select(StudySession).where(StudySession.id == UUID(session_id)))

    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"
    assert finished.json()["remaining_seconds"] == 0
    assert missing.status_code == 404
    assert stored is not None and stored.user_id == student.id
