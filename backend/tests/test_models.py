from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import StudySession, Subject, SubjectMembership, UserProfile


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def seed_subject(session: Session) -> tuple[UserProfile, Subject]:
    user = UserProfile(id=uuid4(), email="learner@example.test")
    session.add(user)
    session.flush()
    subject = Subject(name="Mathematics", created_by=user.id)
    session.add(subject)
    session.flush()
    return user, subject


def test_new_profiles_default_to_student(db_session: Session) -> None:
    profile, _ = seed_subject(db_session)
    assert profile.role == "student"


def test_membership_prevents_duplicate_user_subject_pairs(db_session: Session) -> None:
    profile, subject = seed_subject(db_session)
    membership = SubjectMembership(user_id=profile.id, subject_id=subject.id)
    db_session.add(membership)
    db_session.commit()

    db_session.add(SubjectMembership(user_id=profile.id, subject_id=subject.id))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_database_prevents_two_active_sessions_for_one_user(db_session: Session) -> None:
    profile, subject = seed_subject(db_session)
    end = datetime.now(timezone.utc) + timedelta(minutes=30)
    db_session.add(StudySession(user_id=profile.id, subject_id=subject.id, planned_end_at=end))
    db_session.commit()

    db_session.add(StudySession(user_id=profile.id, subject_id=subject.id, planned_end_at=end))
    with pytest.raises(IntegrityError):
        db_session.commit()
