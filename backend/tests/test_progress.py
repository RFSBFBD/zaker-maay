from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import (
    QuizAttempt,
    StudyQuiz,
    StudySession,
    Subject,
    SubjectMembership,
    UserProfile,
)
from app.db.session import get_db
from app.main import app


def test_progress_is_scoped_to_user_membership_and_aggregates_saved_activity() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    with factory() as db:
        db.add_all([student, admin])
        db.flush()
        physics = Subject(name="Physics", created_by=admin.id)
        biology = Subject(name="Biology", created_by=admin.id)
        db.add_all([physics, biology])
        db.flush()
        db.add(SubjectMembership(user_id=student.id, subject_id=physics.id))
        started = datetime.now(timezone.utc) - timedelta(minutes=30)
        db.add(StudySession(
            user_id=student.id,
            subject_id=physics.id,
            started_at=started,
            planned_end_at=started + timedelta(minutes=25),
            ended_at=started + timedelta(minutes=20),
            status="completed",
        ))
        quiz = StudyQuiz(subject_id=physics.id, created_by=admin.id, title="Motion")
        db.add(quiz)
        db.flush()
        db.add(QuizAttempt(
            quiz_id=quiz.id,
            user_id=student.id,
            score=3,
            total_questions=4,
            answers=[],
        ))
        db.commit()
        physics_id = physics.id

    def override_db() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_profile] = lambda: student
    try:
        response = TestClient(app).get("/api/v1/progress/me")
        assert response.status_code == 200
        body = response.json()
        assert body["study_seconds"] == 1_200
        assert body["quiz_attempts"] == 1
        assert body["quiz_average_percent"] == 75.0
        assert [item["subject_id"] for item in body["subjects"]] == [str(physics_id)]
        assert body["subjects"][0]["study_seconds"] == 1_200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        Base.metadata.drop_all(engine)
        engine.dispose()
