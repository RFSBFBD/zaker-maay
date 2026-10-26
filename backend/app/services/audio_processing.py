import io
import math

from tinytag import TinyTag, TinyTagException

MAX_TRANSCRIPTION_BYTES = 18 * 1024 * 1024
MAX_AUDIO_DURATION_SECONDS = 30 * 60
TRANSCRIBABLE_EXTENSIONS = {".mp3", ".wav", ".m4a"}


class InvalidAudio(ValueError):
    pass


def inspect_audio(content: bytes, extension: str) -> int:
    if extension not in TRANSCRIBABLE_EXTENSIONS:
        raise InvalidAudio("Transcription supports MP3, WAV, and M4A files.")
    if not content or len(content) > MAX_TRANSCRIPTION_BYTES:
        raise InvalidAudio("Audio files for transcription must be no larger than 18 MiB.")
    try:
        metadata = TinyTag.get(file_obj=io.BytesIO(content), tags=False)
        duration = metadata.duration if metadata else None
    except (TinyTagException, OSError, ValueError):
        duration = None
    if duration is None or not math.isfinite(duration) or duration <= 0:
        raise InvalidAudio("The audio duration could not be verified.")
    if duration > MAX_AUDIO_DURATION_SECONDS:
        raise InvalidAudio("Audio transcription is limited to 30 minutes per file.")
    return math.ceil(duration)
