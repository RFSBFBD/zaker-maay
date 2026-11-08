from collections.abc import Generator
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_profile
from app.db.base import Base
from app.db.models import (
    QuizAttempt,
    QuizQuestion,
    Resource,
    ResourceChunk,
    StudyQuiz,
    Subject,
    SubjectMembership,
    UserProfile,
)
from app.db.session import get_db
from app.main import app
from app.services.gemini import GeneratedQuestion, GeneratedQuiz


@pytest.fixture
def quiz_client() -> Generator[tuple[TestClient, Session, UserProfile, UserProfile, Subject, Subject], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    student = UserProfile(id=uuid4(), email="student@example.test", role="student")
    other_student = UserProfile(id=uuid4(), email="other@example.test", role="student")
    admin = UserProfile(id=uuid4(), email="admin@example.test", role="admin")
    db.add_all([student, other_student, admin])
    db.flush()

    math_sub = Subject(name="Calculus", created_by=admin.id)
    private_sub = Subject(name="Quantum", created_by=admin.id)
    db.add_all([math_sub, private_sub])
    db.flush()

    db.add(SubjectMembership(user_id=student.id, subject_id=math_sub.id))
    db.commit()

    def override_db() -> Generator[Session, None, None]:
        with factory() as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_profile] = lambda: student
    try:
        yield TestClient(app), db, student, other_student, math_sub, private_sub
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_profile, None)
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_list_quizzes_empty_and_populated(
    quiz_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, db, student, _, math_sub, _ = quiz_client

    # Empty initially
    resp = client.get(f"/api/v1/subjects/{math_sub.id}/quizzes")
    assert resp.status_code == 200
    assert resp.json() == []

    # Add a quiz with questions
    quiz = StudyQuiz(id=uuid4(), subject_id=math_sub.id, created_by=student.id, title="اختبار التفاضل الأول")
    db.add(quiz)
    db.flush()
    db.add(
        QuizQuestion(
            id=uuid4(),
            quiz_id=quiz.id,
            position=0,
            prompt="ما هي مشتقة x^2؟",
            options=["2x", "x", "2", "x^3"],
            correct_answer=0,
            explanation="مشتقة x^n هي n*x^(n-1)",
        )
    )
    db.commit()

    resp = client.get(f"/api/v1/subjects/{math_sub.id}/quizzes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "اختبار التفاضل الأول"
    assert data[0]["question_count"] == 1


def test_create_quiz_without_passages_fails(
    quiz_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, _, _, _, math_sub, _ = quiz_client
    resp = client.post(f"/api/v1/subjects/{math_sub.id}/quizzes")
    assert resp.status_code == 422
    assert "لا توجد مقاطع نصية كافية" in resp.json()["detail"]


def test_create_quiz_with_passages_succeeds(
    quiz_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, db, student, _, math_sub, _ = quiz_client

    # Add a resource and chunk
    res = Resource(
        subject_id=math_sub.id,
        uploaded_by=student.id,
        file_name="calculus.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        sha256="calc_hash",
        cloudinary_public_id="calc_pub_id",
        secure_url="http://example.com/calc.pdf",
        processing_status="ready",
    )
    db.add(res)
    db.flush()
    db.add(
        ResourceChunk(
            resource_id=res.id,
            chunk_index=0,
            page_number=1,
            content="Calculus derivatives definition: limit of f(x+h)-f(x)/h as h approaches 0.",
        )
    )
    db.commit()

    mock_quiz_draft = GeneratedQuiz(
        title="اختبار المشتقات والتكامل",
        questions=[
            GeneratedQuestion(
                prompt="ما هو تعريف المشتقة رياضياً؟",
                options=["نهاية معدل التغير", "المساحة تحت المنحنى", "قيمة الدالة عند الصفر", "ميل العمودي"],
                correct_answer=0,
                explanation="المشتقة تمثل نهاية معدل التغير اللحظي.",
                source_index=1,
            ),
            GeneratedQuestion(
                prompt="ما هي مشتقة الثابت؟",
                options=["صفر", "واحد", "الثابت نفسه", "غير معرف"],
                correct_answer=0,
                explanation="مشتقة أي دالة ثابتة تساوي صفراً.",
                source_index=1,
            ),
            GeneratedQuestion(
                prompt="ما هي دالة كثير الحدود من الدرجة الأولى؟",
                options=["خط مستقيم", "قطع مكافئ", "دائرة", "نقطة"],
                correct_answer=0,
                explanation="معادلة الخط المستقيم تمثل دالة من الدرجة الأولى.",
                source_index=1,
            ),
        ],
    )

    with patch("app.api.routes.quizzes.safe_call_ai", return_value=mock_quiz_draft):
        resp = client.post(f"/api/v1/subjects/{math_sub.id}/quizzes")
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "اختبار المشتقات والتكامل"
        assert len(data["questions"]) == 3


def test_submit_attempt_and_review(
    quiz_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, db, student, _, math_sub, _ = quiz_client

    # Create quiz directly
    quiz = StudyQuiz(id=uuid4(), subject_id=math_sub.id, created_by=student.id, title="اختبار السرعة")
    db.add(quiz)
    db.flush()

    q1 = QuizQuestion(
        id=uuid4(),
        quiz_id=quiz.id,
        position=0,
        prompt="السؤال 1",
        options=["أ", "ب", "ج", "د"],
        correct_answer=1,
        explanation="شرح 1",
    )
    q2 = QuizQuestion(
        id=uuid4(),
        quiz_id=quiz.id,
        position=1,
        prompt="السؤال 2",
        options=["أ", "ب", "ج", "د"],
        correct_answer=2,
        explanation="شرح 2",
    )
    q3 = QuizQuestion(
        id=uuid4(),
        quiz_id=quiz.id,
        position=2,
        prompt="السؤال 3",
        options=["أ", "ب", "ج", "د"],
        correct_answer=0,
        explanation="شرح 3",
    )
    db.add_all([q1, q2, q3])
    db.commit()

    # Submit with 2 correct, 1 wrong
    payload = {
        "answers": [
            {"question_id": str(q1.id), "selected_answer": 1},  # correct
            {"question_id": str(q2.id), "selected_answer": 0},  # wrong (correct is 2)
            {"question_id": str(q3.id), "selected_answer": 0},  # correct
        ]
    }
    resp = client.post(f"/api/v1/subjects/{math_sub.id}/quizzes/{quiz.id}/attempts", json=payload)
    assert resp.status_code == 201
    result = resp.json()
    assert result["score"] == 2
    assert result["total_questions"] == 3
    assert len(result["review"]) == 3
    assert result["review"][0]["is_correct"] is True
    assert result["review"][1]["is_correct"] is False


def test_unauthorized_subject_access_denied(
    quiz_client: tuple[TestClient, Session, UserProfile, UserProfile, Subject, Subject],
) -> None:
    client, _, _, _, _, private_sub = quiz_client

    resp = client.get(f"/api/v1/subjects/{private_sub.id}/quizzes")
    assert resp.status_code == 404
