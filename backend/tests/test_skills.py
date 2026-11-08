from collections.abc import Generator
from unittest.mock import patch, MagicMock
from uuid import uuid4

import httpx

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import AgentSkill, UserProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture
def skills_client() -> Generator[tuple[TestClient, Session, UserProfile, UserProfile], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    db.add_all([student, admin])
    db.commit()

    def override_db() -> Generator[Session, None, None]:
        with factory() as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_profile] = lambda: admin
    try:
        yield TestClient(app), db, student, admin
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_admin_skills_crud(
    skills_client: tuple[TestClient, Session, UserProfile, UserProfile],
) -> None:
    client, db, _, admin = skills_client

    # Ingest a new skill with mocked GitHub fetch
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "# First Principles Tutor\nAlways break complex ideas into fundamental truths."

    with patch.object(httpx.Client, "get", return_value=mock_resp):
        create_resp = client.post(
            "/api/v1/admin/skills/ingest-github",
            json={
                "github_url": "https://github.com/example/skills/blob/main/first-principles.md",
                "title": "First Principles Tutor",
            },
        )
        assert create_resp.status_code == 200
        skill_id = create_resp.json()["id"]
        assert create_resp.json()["is_active"] is True

    # List skills
    list_resp = client.get("/api/v1/admin/skills")
    assert list_resp.status_code == 200
    skills = list_resp.json()
    assert len(skills) == 1
    assert skills[0]["title"] == "First Principles Tutor"

    # Toggle active
    toggle_resp = client.patch(f"/api/v1/admin/skills/{skill_id}", json={"is_active": False})
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_active"] is False

    # Delete skill
    del_resp = client.delete(f"/api/v1/admin/skills/{skill_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ok"


def test_student_forbidden_from_admin_skills(
    skills_client: tuple[TestClient, Session, UserProfile, UserProfile],
) -> None:
    client, _, student, _ = skills_client
    app.dependency_overrides[get_current_profile] = lambda: student

    resp = client.get("/api/v1/admin/skills")
    assert resp.status_code == 403
