"""Fetch YouTube video transcripts using youtube-transcript-api."""
from __future__ import annotations

import logging

from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)


def fetch_youtube_transcript(video_id: str, languages: list[str] | None = None) -> str | None:
    """Fetch transcript/captions for a YouTube video. Returns text or None if unavailable."""
    try:
        if not languages:
            languages = ["ar", "en", "hi", "es", "fr", "ru", "de", "ja", "ko", "tr"]
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except Exception:
                continue
        if transcript is None:
            auto_generated = transcript_list.find_auto_transcript(languages)
            if auto_generated:
                transcript = auto_generated
        if transcript is None:
            return None
        text_parts = []
        for entry in transcript.fetch():
            text_parts.append(entry.get("text", "").strip())
        full_text = "\n".join(text_parts)
        return full_text if full_text.strip() else None
    except Exception as exc:
        logger.warning("Failed to fetch transcript for video %s: %s", video_id, exc)
        return None
