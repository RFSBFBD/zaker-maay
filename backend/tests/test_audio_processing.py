import io
from types import SimpleNamespace
import wave

import pytest

from app.services import audio_processing
from app.services.audio_processing import InvalidAudio


def _one_second_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(1)
        audio.setframerate(8_000)
        audio.writeframes(bytes([128]) * 8_000)
    return output.getvalue()


def test_inspect_audio_verifies_duration_from_wav_metadata() -> None:
    assert audio_processing.inspect_audio(_one_second_wav(), ".wav") == 1


def test_inspect_audio_rejects_unsupported_format() -> None:
    with pytest.raises(InvalidAudio, match="supports MP3, WAV, and M4A"):
        audio_processing.inspect_audio(b"audio", ".webm")


def test_inspect_audio_rejects_unverified_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio_processing.TinyTag, "get", lambda **kwargs: None)
    with pytest.raises(InvalidAudio, match="duration could not be verified"):
        audio_processing.inspect_audio(b"audio", ".mp3")


def test_inspect_audio_rejects_duration_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        audio_processing.TinyTag,
        "get",
        lambda **kwargs: SimpleNamespace(duration=audio_processing.MAX_AUDIO_DURATION_SECONDS + 1),
    )
    with pytest.raises(InvalidAudio, match="limited to 30 minutes"):
        audio_processing.inspect_audio(b"audio", ".mp3")


def test_inspect_audio_rejects_oversized_input() -> None:
    with pytest.raises(InvalidAudio, match="18 MiB"):
        audio_processing.inspect_audio(b"x" * (audio_processing.MAX_TRANSCRIPTION_BYTES + 1), ".wav")
