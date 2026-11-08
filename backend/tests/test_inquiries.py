from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import StudentInquiry, Subject, SubjectMembership, UserProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture
def inquiry_client() -> Generator[tuple[TestClient, Session, UserProfile, UserProfile, Subject], None, None]:
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

    subject = Subject(name="Database Systems", created_by=admin.id)
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
        yield TestClient(app), db, student, admin, subject
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_student_inquiries_workflow(
    inquiry_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject],
) -> None:
    client, db, student, admin, subject = inquiry_client

    # Add an inquiry
    inq = StudentInquiry(
        id=uuid4(),
        subject_id=subject.id,
        student_id=student.id,
        question="هل سيشمل الاختبار الفصلي التطبيع حتى BCNF؟",
        ai_suggested_answer="هذا سؤال إداري",
        status="pending",
        is_read=False,
    )
    db.add(inq)
    db.commit()

    # Student views their inquiries
    resp = client.get("/api/v1/inquiries/me")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["inquiries"]) == 1
    assert data["unread_count"] == 0  # Pending does not count as unread answered

    # Admin responds
    app.dependency_overrides[get_current_profile] = lambda: admin
    admin_resp = client.post(
        f"/api/v1/inquiries/admin/{inq.id}/respond",
        json={
            "status": "approved",
            "admin_answer": "نعم، حتى النموذج العادي BCNF مقرر في الامتحان.",
            "admin_notes": "تم توضيح ذلك في المحاضرة 4",
        },
    )
    assert admin_resp.status_code == 200
    assert admin_resp.json()["status"] == "approved"
    assert admin_resp.json()["admin_answer"] == "نعم، حتى النموذج العادي BCNF مقرر في الامتحان."

    # Student checks again -> unread_count is now 1
    app.dependency_overrides[get_current_profile] = lambda: student
    resp2 = client.get("/api/v1/inquiries/me")
    assert resp2.status_code == 200
    assert resp2.json()["unread_count"] == 1
    assert resp2.json()["inquiries"][0]["admin_answer"] is not None

    # Student marks all read
    mark_resp = client.post("/api/v1/inquiries/mark-all-read")
    assert mark_resp.status_code == 200
    assert mark_resp.json()["marked"] == 1

    # Now unread_count is 0
    resp3 = client.get("/api/v1/inquiries/me")
    assert resp3.json()["unread_count"] == 0


def test_student_cannot_access_admin_inquiries(
    inquiry_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject],
) -> None:
    client, _, student, _, _ = inquiry_client
    # Profile is student
    resp = client.get("/api/v1/inquiries/admin/all")
    assert resp.status_code == 403
