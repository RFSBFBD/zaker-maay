from __future__ import annotations

import uuid
from typing import Generator
from unittest.mock import patch

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
def image_gen_client() -> Generator[tuple[TestClient, Session, UserProfile, Subject], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db_session = factory()

    profile = UserProfile(
        id=uuid.uuid4(),
        email="artstudent@example.com",
        display_name="Art Student",
        role="student",
    )
    db_session.add(profile)

    subject = Subject(
        id=uuid.uuid4(),
        name="Biology 101",
        description="Introduction to Cell Biology",
        created_by=profile.id,
    )
    db_session.add(subject)

    membership = SubjectMembership(
        subject_id=subject.id,
        user_id=profile.id,
        role="student",
    )
    db_session.add(membership)
    db_session.commit()

    def override_db() -> Generator[Session, None, None]:
        with factory() as request_session:
            yield request_session

    client = TestClient(app)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_profile] = lambda: profile

    yield client, db_session, profile, subject

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_generate_image_unauthorized():
    client = TestClient(app)
    fake_sub_id = uuid.uuid4()
    resp = client.post(
        f"/api/v1/subjects/{fake_sub_id}/images/generate",
        json={"prompt": "Cell mitosis diagram"},
    )
    assert resp.status_code == 401


def test_generate_image_validation_error(image_gen_client):
    client, _, _, subject = image_gen_client
    resp = client.post(
        f"/api/v1/subjects/{subject.id}/images/generate",
        json={"prompt": "a"},  # min length is 2
    )
    assert resp.status_code == 422


def test_generate_image_success(image_gen_client):
    client, _, _, subject = image_gen_client

    mock_result = {
        "type": "svg",
        "svg": "<svg><rect width='100' height='100'/></svg>",
        "title": "Cell mitosis diagram",
        "description": "Educational diagram for cell mitosis",
    }

    with patch("app.services.gemini.generate_concept_illustration", return_value=mock_result):
        resp = client.post(
            f"/api/v1/subjects/{subject.id}/images/generate",
            json={"prompt": "Cell mitosis diagram", "context": "Stages of cell division"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "svg"
        assert "<svg" in data["svg"]
        assert data["title"] == "Cell mitosis diagram"
