from collections.abc import Generator
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import (
    ChatMessage,
    ChatThread,
    Resource,
    ResourceChunk,
    Subject,
    SubjectMembership,
    UserProfile,
)
from app.db.session import get_db
from app.main import app


@pytest.fixture
def chat_client() -> Generator[tuple[TestClient, Session, UserProfile, UserProfile, Subject], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    student1 = UserProfile(id=uuid4(), email="student1@example.test", role="student")
    student2 = UserProfile(id=uuid4(), email="student2@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    db.add_all([student1, student2, admin])
    db.flush()

    subject = Subject(name="Operating Systems", created_by=admin.id)
    db.add(subject)
    db.flush()
    db.add_all([
        SubjectMembership(user_id=student1.id, subject_id=subject.id),
        SubjectMembership(user_id=student2.id, subject_id=subject.id),
    ])
    db.commit()

    def override_db() -> Generator[Session, None, None]:
        with factory() as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_profile] = lambda: student1
    try:
        yield TestClient(app), db, student1, student2, subject
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_chat_no_resources_returns_friendly_prompt(
    chat_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject],
) -> None:
    client, _, student1, _, subject = chat_client

    resp = client.post(
        f"/api/v1/subjects/{subject.id}/chat",
        json={"message": "ما هو الـ Process؟"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["no_resources"] is True
    assert "لم تقم برفع أي ملفات" in data["answer"]
    assert "thread_id" in data


def test_thread_management_lifecycle(
    chat_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject],
) -> None:
    client, _, student1, _, subject = chat_client

    # Create thread
    created = client.post(
        f"/api/v1/subjects/{subject.id}/chat/threads",
        json={"title": "محادثة المعالج والذاكرة"},
    )
    assert created.status_code == 200
    thread_id = created.json()["id"]

    # List threads
    listed = client.get(f"/api/v1/subjects/{subject.id}/chat/threads")
    assert listed.status_code == 200
    threads = listed.json()
    assert any(t["id"] == thread_id for t in threads)

    # Pin thread
    pinned = client.patch(f"/api/v1/subjects/{subject.id}/chat/threads/{thread_id}/pin")
    assert pinned.status_code == 200
    assert pinned.json()["is_pinned"] is True

    # Delete thread
    deleted = client.delete(f"/api/v1/subjects/{subject.id}/chat/threads/{thread_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "ok"

    # Ensure deleted
    after_list = client.get(f"/api/v1/subjects/{subject.id}/chat/threads")
    assert all(t["id"] != thread_id for t in after_list.json())


def test_student_isolation_in_chat_threads(
    chat_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject],
) -> None:
    client, db, student1, student2, subject = chat_client

    # Student 1 creates thread
    thread = ChatThread(
        id=uuid4(),
        subject_id=subject.id,
        student_id=student1.id,
        title="جلسة الطالب الأول",
    )
    db.add(thread)
    db.commit()

    # Switch to Student 2
    app.dependency_overrides[get_current_profile] = lambda: student2

    # Student 2 should not see Student 1's thread in list
    listed = client.get(f"/api/v1/subjects/{subject.id}/chat/threads")
    assert listed.status_code == 200
    assert all(t["id"] != str(thread.id) for t in listed.json())

    # Student 2 cannot read Student 1's messages
    msg_resp = client.get(f"/api/v1/subjects/{subject.id}/chat/threads/{thread.id}/messages")
    assert msg_resp.status_code == 404


def test_chat_with_resources_invokes_agent_and_persists(
    chat_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject],
) -> None:
    client, db, student1, _, subject = chat_client

    # Add a ready resource
    resource = Resource(
        subject_id=subject.id,
        uploaded_by=student1.id,
        file_name="processes.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256="dummy_sha256",
        cloudinary_public_id="dummy_public_id",
        secure_url="http://dummy.url",
        processing_status="ready",
    )
    db.add(resource)
    db.flush()
    db.add(
        ResourceChunk(
            resource_id=resource.id,
            chunk_index=0,
            page_number=1,
            content="A process is a program in execution containing program counter and registers.",
        )
    )
    db.commit()

    # Mock orchestrator response
    from app.services.orchestrator import OrchestratorResult

    mock_result = OrchestratorResult(
        success=True,
        plan=[],
        results={"chat_qa": "العملية (Process) هي برنامج قيد التنفيذ في الذاكرة."},
    )

    with patch("app.api.routes.subject_chat.orchestrate_chat", return_value=mock_result), \
         patch("app.api.routes.subject_chat.gemini_service.generate_follow_up_suggestions", return_value=["ما هي حالات الـ Process؟"]):
        resp = client.post(
            f"/api/v1/subjects/{subject.id}/chat",
            json={"message": "ما هو الـ Process؟"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "العملية (Process)" in data["answer"]
        assert len(data["suggested_replies"]) == 1
        assert data["thread_id"] is not None

        # Check persistence in database
        thread_msgs = client.get(f"/api/v1/subjects/{subject.id}/chat/threads/{data['thread_id']}/messages")
        assert thread_msgs.status_code == 200
        messages = thread_msgs.json()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
