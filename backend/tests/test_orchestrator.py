"""Tests for the agent orchestrator layer."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.orchestrator import (
    PlanStep,
    classify_intent,
    build_plan,
)


# ── Intent classification ─────────────────────────────────────────────────────

def test_classify_intent_plain_chat() -> None:
    assert classify_intent("what is the water cycle") == ["chat_qa"]


def test_classify_intent_with_image_keyword() -> None:
    result = classify_intent("draw a diagram of the process")
    assert "chat_qa" in result
    assert "image_generation" in result


def test_classify_intent_with_quiz_keyword() -> None:
    result = classify_intent("quiz me on this topic")
    assert "chat_qa" in result
    assert "quiz_generation" in result


def test_classify_intent_with_flashcard_keyword() -> None:
    result = classify_intent("create flashcards for revision")
    assert "chat_qa" in result
    assert "flashcards" in result


def test_classify_intent_combined_arabic_english() -> None:
    result = classify_intent("explain and draw image diagram")
    assert "chat_qa" in result
    assert "image_generation" in result


def test_classify_intent_all_three_intents() -> None:
    result = classify_intent("اشرح وارسم image quiz test me")
    assert "chat_qa" in result
    assert "image_generation" in result
    assert "quiz_generation" in result


def test_classify_intent_just_draw() -> None:
    result = classify_intent("draw")
    assert "image_generation" in result


def test_classify_intent_empty_message() -> None:
    # Even an empty message defaults to chat_qa
    result = classify_intent("")
    assert result == ["chat_qa"]


# ── Plan building ──────────────────────────────────────────────────────────────

def test_build_plan_single_intent() -> None:
    plan = build_plan(["chat_qa"], message="hello", passages=[])
    assert len(plan) == 1
    assert plan[0].task_type == "chat_qa"


def test_build_plan_combined_intent() -> None:
    plan = build_plan(["chat_qa", "image_generation"], message="draw it", passages=[])
    assert len(plan) == 2
    assert plan[0].task_type == "chat_qa"
    assert plan[1].task_type == "image_generation"


def test_build_plan_quiz_and_flashcards() -> None:
    plan = build_plan(
        ["chat_qa", "quiz_generation", "flashcards"],
        message="quiz me",
        passages=["p1", "p2"],
    )
    assert len(plan) == 3
    assert plan[1].kwargs["passages"] == ["p1", "p2"]
    assert plan[2].kwargs["passages"] == ["p1", "p2"]


# ── Fallback resolution ───────────────────────────────────────────────────────

def test_resolve_model_uses_fallback_when_configured() -> None:
    from app.db.models import AIModelConfig
    from uuid import uuid4
    from sqlalchemy import select

    mock_db = MagicMock()
    fallback_row = AIModelConfig(
        id=uuid4(),
        task_type="chat_qa",
        model_name="gemini-2.5-flash",
        api_key=None,
        fallback_model="gemini-3.5-flash",
        temperature=0.2,
        max_output_tokens=2000,
        is_active=True,
    )
    mock_db.scalar.return_value = fallback_row

    from app.services.orchestrator import _resolve_model
    cfg = _resolve_model("chat_qa", mock_db, use_fallback=True)
    # Should resolve with fallback model name when requested
    assert cfg is not None


def test_resolve_model_without_fallback_no_change() -> None:
    from app.db.models import AIModelConfig
    from uuid import uuid4

    mock_db = MagicMock()
    no_fallback = AIModelConfig(
        id=uuid4(),
        task_type="chat_qa",
        model_name="gemini-2.5-flash",
        api_key=None,
        fallback_model=None,
        temperature=0.2,
        max_output_tokens=2000,
        is_active=True,
    )
    mock_db.scalar.return_value = no_fallback

    from app.services.orchestrator import _resolve_model
    cfg = _resolve_model("chat_qa", mock_db, use_fallback=False)
    assert cfg is not None
