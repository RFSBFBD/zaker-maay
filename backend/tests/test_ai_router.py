import pytest

from app.services.ai_router import safe_call_ai


def test_safe_call_ai_passes_db_to_supported_generators() -> None:
    marker = object()
    received: list[object] = []

    def generate(value: str, *, db: object | None = None) -> str:
        received.append(db)
        return value

    assert safe_call_ai(generate, "draft", db=marker) == "draft"
    assert received == [marker]


def test_safe_call_ai_supports_test_generators_without_db() -> None:
    def generate(value: str) -> str:
        return value.upper()

    assert safe_call_ai(generate, "draft", db=object()) == "DRAFT"


def test_safe_call_ai_does_not_retry_internal_type_error() -> None:
    calls = 0

    def generate(*, db: object | None = None) -> None:
        nonlocal calls
        calls += 1
        raise TypeError("failure inside generator")

    with pytest.raises(TypeError, match="failure inside generator"):
        safe_call_ai(generate, db=object())

    assert calls == 1


# ── AI Agent Intent Routing Tests ─────────────────────────────────────────────

def test_agent_intent_avoids_false_positive_on_phrasings() -> None:
    from app.services.ai_router import classify_agent_intent

    # The user's exact phrase containing "بشكل لوجيك" must NOT trigger image generation
    user_prompt = "بقولك ايه عايز احل مشكله ال ai router عايزه يبقي ai agent تمام و يجاوب بشكل لوجيك فاهمني"
    assert classify_agent_intent(user_prompt) == ["chat_qa"]

    # Phrasings with "بشكل", "توضيحي", "صورة عامة", "تخطيط" must NOT trigger image generation
    assert classify_agent_intent("اشرح لي دورة كريبس بشكل مبسط ومفهوم") == ["chat_qa"]
    assert classify_agent_intent("وضح لي بمثال توضيحي قانون نيوتن الثالث") == ["chat_qa"]
    assert classify_agent_intent("اعطني صورة عامة عن المنهج الدراسي") == ["chat_qa"]
    assert classify_agent_intent("هل الرسم ده مقرر علينا في الامتحان؟") == ["chat_qa"]
    assert classify_agent_intent("عايز تخطيط المذاكرة للأسبوع القادم") == ["chat_qa"]


def test_agent_intent_triggers_explicit_image_requests() -> None:
    from app.services.ai_router import classify_agent_intent

    # Explicit requests for illustrations or diagrams must trigger image_generation
    r1 = classify_agent_intent("ارسم لي مخطط يوضح دورة كريبس")
    assert "image_generation" in r1
    assert "chat_qa" in r1

    r2 = classify_agent_intent("اعمل لي رسمة لشكل القلب ومكوناته")
    assert "image_generation" in r2

    r3 = classify_agent_intent("عايز رسم توضيحي لخلية نباتية")
    assert "image_generation" in r3

    r4 = classify_agent_intent("draw a diagram of photosynthesis")
    assert "image_generation" in r4


def test_agent_intent_multi_intent() -> None:
    from app.services.ai_router import classify_agent_intent

    # Multi-intent: explain, draw, and quiz
    res = classify_agent_intent("اشرح لي الدرس وارسم مخطط توضيحي واختبرني فيه")
    assert "chat_qa" in res
    assert "image_generation" in res
    assert "quiz_generation" in res
