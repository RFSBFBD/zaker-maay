from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import AIModelConfig, Subject, UserProfile
from app.db.session import get_db
from app.main import app
from app.services.ai_router import resolve_ai_config


@pytest.fixture
def client_and_profiles() -> Generator[tuple[TestClient, UserProfile, UserProfile], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    with factory() as session:
        session.add_all([student, admin])
        session.commit()

    def override_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), student, admin
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_student_forbidden_from_admin_endpoints(
    client_and_profiles: tuple[TestClient, UserProfile, UserProfile],
) -> None:
    client, student, _ = client_and_profiles
    app.dependency_overrides[get_current_profile] = lambda: student

    analytics = client.get("/api/v1/admin/analytics")
    users = client.get("/api/v1/admin/users")
    ai_configs = client.get("/api/v1/admin/ai-configs")

    assert analytics.status_code == 403
    assert users.status_code == 403
    assert ai_configs.status_code == 403


def test_admin_can_access_analytics_and_users(
    client_and_profiles: tuple[TestClient, UserProfile, UserProfile],
) -> None:
    client, student, admin = client_and_profiles
    app.dependency_overrides[get_current_profile] = lambda: admin

    analytics = client.get("/api/v1/admin/analytics")
    assert analytics.status_code == 200
    data = analytics.json()
    assert data["total_users"] == 2
    assert data["students_count"] == 1
    assert data["admins_count"] == 1
    assert "task_models" in data

    users = client.get("/api/v1/admin/users")
    assert users.status_code == 200
    assert len(users.json()) == 2

    # Promote student to admin
    role_change = client.patch(
        f"/api/v1/admin/users/{student.id}/role",
        json={"role": "admin"},
    )
    assert role_change.status_code == 200
    assert role_change.json()["role"] == "admin"


def test_admin_can_manage_ai_task_configs_and_router_resolves_it(
    client_and_profiles: tuple[TestClient, UserProfile, UserProfile],
) -> None:
    client, _, admin = client_and_profiles
    app.dependency_overrides[get_current_profile] = lambda: admin

    # List default configs
    configs_res = client.get("/api/v1/admin/ai-configs")
    assert configs_res.status_code == 200
    configs = configs_res.json()
    assert len(configs) >= 6

    # Configure a specialized low-token model for quiz_generation
    save_res = client.post(
        "/api/v1/admin/ai-configs",
        json={
            "task_type": "quiz_generation",
            "model_name": "gemini-1.5-flash",
            "temperature": 0.1,
            "max_output_tokens": 1500,
            "is_active": True,
            "description": "نموذج توفير التوكنز السريع للاختبارات",
        },
    )
    assert save_res.status_code == 200
    assert save_res.json()["model_name"] == "gemini-1.5-flash"

    # Test router resolution from DB session
    session_gen = app.dependency_overrides[get_db]()
    session = next(session_gen)
    try:
        resolved = resolve_ai_config("quiz_generation", db=session)
        assert resolved.model_name == "gemini-1.5-flash"
        assert resolved.temperature == 0.1
        assert resolved.max_output_tokens == 1500
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass
