from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.api.routes import assistant as assistant_route
from app.api.routes import quizzes as quizzes_route
from app.db.base import Base
from app.db.models import QuizAttempt, Resource, ResourceChunk, Subject, SubjectMembership, UserProfile
from app.db.session import get_db
from app.main import app
from app.services.gemini import GeneratedQuiz, GeneratedQuestion


@pytest.fixture
def assistant_client() -> Generator[tuple[TestClient, Session, UserProfile, Subject, Subject], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    student = UserProfile(id=uuid4(), role="student")
    admin = UserProfile(id=uuid4(), role="admin")
    db.add_all([student, admin])
    db.flush()
    physics = Subject(name="Physics", created_by=admin.id)
    biology = Subject(name="Biology", created_by=admin.id)
    db.add_all([physics, biology])
    db.flush()
    db.add_all(
        [
            SubjectMembership(user_id=student.id, subject_id=physics.id),
            SubjectMembership(user_id=student.id, subject_id=biology.id),
        ]
    )
    for subject, name, content, digest in [
        (physics, "physics.txt", "Magnetism creates magnetic fields around a magnet.", "1" * 64),
        (biology, "biology.txt", "Photosynthesis transforms light into chemical energy.", "2" * 64),
    ]:
        resource = Resource(
            subject_id=subject.id,
            uploaded_by=student.id,
            file_name=name,
            mime_type="text/plain",
            size_bytes=len(content),
            sha256=digest,
            cloudinary_public_id=f"library/{name}",
            secure_url="https://private.invalid/resource",
            processing_status="ready",
        )
        db.add(resource)
        db.flush()
        db.add(ResourceChunk(resource_id=resource.id, chunk_index=0, content=content))
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


def test_assistant_passes_only_requested_subject_sources_to_gemini(
    assistant_client: tuple[TestClient, Session, UserProfile, Subject, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _, physics, _ = assistant_client
    captured = {}

    def fake_generate(question, passages):
        captured["question"] = question
        captured["files"] = [passage.file_name for passage in passages]
        return "A magnet creates a magnetic field [S1]."

    monkeypatch.setattr(assistant_route, "generate_grounded_answer", fake_generate)

    response = client.post(
        f"/api/v1/subjects/{physics.id}/assistant/ask", json={"question": "What creates magnetic fields?"}
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "A magnet creates a magnetic field [S1]."
    assert [source["file_name"] for source in response.json()["sources"]] == ["physics.txt"]
    assert captured == {"question": "What creates magnetic fields?", "files": ["physics.txt"]}


def test_assistant_does_not_call_gemini_without_relevant_evidence(
    assistant_client: tuple[TestClient, Session, UserProfile, Subject, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _, physics, _ = assistant_client

    def unexpected_generate(*args, **kwargs):
        pytest.fail("Gemini must not be called when retrieval finds no evidence.")

    monkeypatch.setattr(assistant_route, "generate_grounded_answer", unexpected_generate)
    response = client.post(
        f"/api/v1/subjects/{physics.id}/assistant/ask", json={"question": "Who discovered Pluto?"}
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []
    assert "لم أجد معلومات" in response.json()["answer"]


def test_generated_quiz_hides_answer_key_then_persists_server_scored_attempt(
    assistant_client: tuple[TestClient, Session, UserProfile, Subject, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db, student, physics, _ = assistant_client
    draft = GeneratedQuiz(
        title="اختبار المجالات المغناطيسية",
        questions=[
            GeneratedQuestion(
                prompt=f"سؤال رقم {index + 1} عن المجالات المغناطيسية؟",
                options=["الإجابة الصحيحة", "الخيار ب", "الخيار ج", "الخيار د"],
                correct_answer=0,
                explanation="المصدر يوضح أن المغناطيس يولد مجالًا مغناطيسيًا.",
                source_index=1,
            )
            for index in range(3)
        ],
    )
    monkeypatch.setattr(quizzes_route, "generate_quiz_draft", lambda passages: draft)

    created = client.post(f"/api/v1/subjects/{physics.id}/quizzes")

    assert created.status_code == 201
    quiz = created.json()
    assert len(quiz["questions"]) == 3
    assert all("correct_answer" not in question for question in quiz["questions"])
    assert all(question["source_file"] == "physics.txt" for question in quiz["questions"])
    answers = [
        {"question_id": question["id"], "selected_answer": 0}
        for question in quiz["questions"]
    ]

    submitted = client.post(
        f"/api/v1/subjects/{physics.id}/quizzes/{quiz['id']}/attempts",
        json={"answers": answers},
    )

    assert submitted.status_code == 201
    result = submitted.json()
    assert result["score"] == 3
    assert result["total_questions"] == 3
    assert all(review["is_correct"] for review in result["review"])
    assert len(db.scalars(select(QuizAttempt).where(QuizAttempt.user_id == student.id)).all()) == 1
    history = client.get(f"/api/v1/subjects/{physics.id}/quizzes/{quiz['id']}/attempts")
    assert history.status_code == 200 and history.json()[0]["score"] == 3


def test_quiz_submission_requires_exact_question_set(
    assistant_client: tuple[TestClient, Session, UserProfile, Subject, Subject], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _, physics, _ = assistant_client
    draft = GeneratedQuiz(
        title="اختبار",
        questions=[
            GeneratedQuestion(
                prompt=f"سؤال رقم {index + 1}؟",
                options=["أ", "ب", "ج", "د"],
                correct_answer=0,
                explanation="الشرح",
                source_index=1,
            )
            for index in range(3)
        ],
    )
    monkeypatch.setattr(quizzes_route, "generate_quiz_draft", lambda passages: draft)
    quiz = client.post(f"/api/v1/subjects/{physics.id}/quizzes").json()

    response = client.post(
        f"/api/v1/subjects/{physics.id}/quizzes/{quiz['id']}/attempts",
        json={"answers": [{"question_id": quiz["questions"][0]["id"], "selected_answer": 0}]},
    )

    assert response.status_code == 422
