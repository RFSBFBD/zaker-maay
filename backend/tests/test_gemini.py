from types import SimpleNamespace
from uuid import uuid4

from app.services import gemini
from app.services.retrieval import RetrievedPassage


def test_gemini_prompt_uses_only_retrieved_sources_and_closes_client(monkeypatch) -> None:
    captured = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(text="Evidence-based answer [S1].")

    class FakeClient:
        def __init__(self, **kwargs):
            captured["api_key"] = kwargs["api_key"]
            self.models = FakeModels()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(gemini, "genai", SimpleNamespace(Client=FakeClient))
    monkeypatch.setattr(
        gemini,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key="test-key", gemini_model="test-model"),
    )
    passage = RetrievedPassage(
        resource_id=uuid4(),
        file_name="source.txt",
        page_number=None,
        chunk_index=0,
        content="Matter is made of particles.",
        score=1.0,
    )

    answer = gemini.generate_grounded_answer("What is matter?", [passage])

    assert answer == "Evidence-based answer [S1]."
    assert captured["model"] == "test-model"
    assert "Matter is made of particles." in captured["contents"]
    assert captured["closed"] is True


def test_audio_transcription_uses_explicit_input_and_structured_language(monkeypatch) -> None:
    captured = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(parsed=gemini.GeneratedTranscript(language="Arabic", transcript="نص مسموع."))

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(gemini, "genai", SimpleNamespace(Client=FakeClient))
    monkeypatch.setattr(
        gemini,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key="test-key", gemini_model="test-model"),
    )

    transcript = gemini.transcribe_audio(b"RIFF-audio", "audio/wav")

    assert transcript.language == "Arabic"
    assert transcript.transcript == "نص مسموع."
    assert captured["model"] == "test-model"
    assert "Do not summarize" in captured["contents"][0]
    assert captured["contents"][1].inline_data.mime_type == "audio/wav"
    assert captured["config"].response_mime_type == "application/json"
    assert captured["closed"] is True
