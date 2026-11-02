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
