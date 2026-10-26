from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import Subject, SubjectMembership, UserProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client_and_users() -> Generator[tuple[TestClient, UserProfile, UserProfile, Subject, Subject], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    with factory() as session:
        session.add_all([student, admin])
        session.flush()
        member_subject = Subject(name="Physics", created_by=admin.id)
        private_subject = Subject(name="Biology", created_by=admin.id)
        session.add_all([member_subject, private_subject])
        session.flush()
        session.add(SubjectMembership(user_id=student.id, subject_id=member_subject.id))
        session.commit()
        session.refresh(member_subject)
        session.refresh(private_subject)

    def override_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), student, admin, member_subject, private_subject
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def use_profile(profile: UserProfile) -> None:
    app.dependency_overrides[get_current_profile] = lambda: profile


def test_student_only_lists_and_reads_joined_subjects(
    client_and_users: tuple[TestClient, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, student, _, member_subject, private_subject = client_and_users
    use_profile(student)

    listed = client.get("/api/v1/subjects")
    private = client.get(f"/api/v1/subjects/{private_subject.id}")
    visible = client.get(f"/api/v1/subjects/{member_subject.id}")

    assert listed.status_code == 200
    # Student can only see subjects they are enrolled in
    listed_ids = [item["id"] for item in listed.json()]
    assert str(member_subject.id) in listed_ids
    assert str(private_subject.id) not in listed_ids
    assert private.status_code == 404
    assert visible.status_code == 200


def test_student_can_create_subject_and_is_enrolled(
    client_and_users: tuple[TestClient, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, student, _, _, _ = client_and_users
    use_profile(student)

    response = client.post("/api/v1/subjects", json={"name": "Chemistry"})

    assert response.status_code == 201
    subject_id = response.json()["id"]

    # Student should automatically see the new subject (they are enrolled as creator)
    visible = client.get(f"/api/v1/subjects/{subject_id}")
    assert visible.status_code == 200
    assert visible.json()["name"] == "Chemistry"

    # Also appears in the list
    listed = client.get("/api/v1/subjects")
    assert listed.status_code == 200
    listed_ids = [item["id"] for item in listed.json()]
    assert subject_id in listed_ids


def test_student_can_update_and_archive_own_subject(
    client_and_users: tuple[TestClient, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, student, _, _, _ = client_and_users
    use_profile(student)

    created = client.post("/api/v1/subjects", json={"name": "My Subject"})
    assert created.status_code == 201
    sid = created.json()["id"]

    updated = client.patch(f"/api/v1/subjects/{sid}", json={"description": "My notes"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "My notes"

    archived = client.delete(f"/api/v1/subjects/{sid}")
    assert archived.status_code == 204
    assert client.get(f"/api/v1/subjects/{sid}").status_code == 404


def test_student_cannot_update_another_users_subject(
    client_and_users: tuple[TestClient, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, student, _, member_subject, _ = client_and_users
    use_profile(student)

    # member_subject was created by admin — student cannot update it
    updated = client.patch(f"/api/v1/subjects/{member_subject.id}", json={"description": "Hacked"})
    assert updated.status_code == 403


def test_admin_can_create_update_and_delete_subject(
    client_and_users: tuple[TestClient, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, _, admin, _, _ = client_and_users
    use_profile(admin)

    created = client.post("/api/v1/subjects", json={"name": "  Chemistry  "})
    assert created.status_code == 201
    assert created.json()["name"] == "Chemistry"
    subject_id = UUID(created.json()["id"])

    updated = client.patch(f"/api/v1/subjects/{subject_id}", json={"description": "Atomic structure"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "Atomic structure"

    deleted = client.delete(f"/api/v1/subjects/{subject_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/subjects/{subject_id}").status_code == 404


def test_subject_name_cannot_be_blank(
    client_and_users: tuple[TestClient, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, _, admin, _, _ = client_and_users
    use_profile(admin)

    response = client.post("/api/v1/subjects", json={"name": "   "})

    assert response.status_code == 422


def test_admin_cannot_create_duplicate_normalized_subject_name(
    client_and_users: tuple[TestClient, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, _, admin, _, _ = client_and_users
    use_profile(admin)

    first = client.post("/api/v1/subjects", json={"name": "Chemistry"})
    duplicate = client.post("/api/v1/subjects", json={"name": " chemistry "})

    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_admin_can_manage_subject_membership(
    client_and_users: tuple[TestClient, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, student, admin, _, private_subject = client_and_users
    use_profile(admin)

    added = client.post(
        f"/api/v1/subjects/{private_subject.id}/members",
        json={"user_id": str(student.id)},
    )
    duplicate = client.post(
        f"/api/v1/subjects/{private_subject.id}/members",
        json={"user_id": str(student.id)},
    )
    removed = client.delete(f"/api/v1/subjects/{private_subject.id}/members/{student.id}")

    assert added.status_code == 201
    assert added.json()["role"] == "student"
    assert duplicate.status_code == 409
    assert removed.status_code == 204
