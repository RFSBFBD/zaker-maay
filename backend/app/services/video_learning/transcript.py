from __future__ import annotations

import logging
import re
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi

from app.services.video_learning.schemas import TimestampedTranscriptSegment

logger = logging.getLogger(__name__)

ARABIC_CHAR_PATTERN = re.compile(r"[\u0600-\u06ff]")


def detect_transcript_language(text: str) -> str:
    """Detect whether text is predominantly Arabic or English/other."""
    arabic_chars = len(ARABIC_CHAR_PATTERN.findall(text))
    total_alpha = len([c for c in text if c.isalpha()])
    if total_alpha > 0 and (arabic_chars / total_alpha) > 0.3:
        return "ar"
    return "en"


def fetch_timestamped_transcript(
    video_id: str,
    languages: list[str] | None = None,
) -> tuple[list[TimestampedTranscriptSegment], str] | None:
    """Fetch real captions with exact timestamps from YouTube.
    
    Returns (segments, detected_language) or None if unavailable.
    Never fabricates transcript text or timestamps.
    """
    if not languages:
        languages = ["ar", "en", "en-US", "en-GB", "es", "fr", "de", "tr"]

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None

        # 1. Try manual transcripts first
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except Exception:
                continue

        # 2. Try auto-generated captions if no manual transcript
        if transcript is None:
            try:
                transcript = transcript_list.find_auto_transcript(languages)
            except Exception:
                pass

        if transcript is None:
            return None

        raw_entries = transcript.fetch()
        if not raw_entries:
            return None

        full_text_sample = " ".join(e.get("text", "") for e in raw_entries[:40])
        detected_lang = detect_transcript_language(full_text_sample)

        # Build timestamped segments
        segments: list[TimestampedTranscriptSegment] = []
        for entry in raw_entries:
            text = (entry.get("text") or "").strip()
            if not text:
                continue
            start = float(entry.get("start", 0.0))
            duration = float(entry.get("duration", 0.0))
            end = round(start + duration, 2)

            segments.append(
                TimestampedTranscriptSegment(
                    text=text,
                    start_seconds=round(start, 2),
                    duration_seconds=round(duration, 2),
                    end_seconds=end,
                    confidence=1.0,
                )
            )

        if not segments:
            return None

        return segments, detected_lang

    except Exception as exc:
        logger.warning("Could not fetch timestamped transcript for video %s: %s", video_id, exc)
        return None


def group_transcript_into_lesson_sections(
    raw_segments: list[TimestampedTranscriptSegment],
    window_duration_seconds: float = 60.0,
) -> list[dict[str, Any]]:
    """Group fine-grained subtitle lines into coherent topical sections with start/end bounds."""
    if not raw_segments:
        return []

    sections: list[dict[str, Any]] = []
    current_lines: list[str] = []
    current_start = raw_segments[0].start_seconds
    current_end = raw_segments[0].end_seconds

    for seg in raw_segments:
        current_lines.append(seg.text)
        current_end = seg.end_seconds

        # Group when time window reached or strong topic boundary
        if (current_end - current_start) >= window_duration_seconds:
            combined_text = " ".join(current_lines).strip()
            if combined_text:
                sections.append({
                    "start_seconds": current_start,
                    "end_seconds": current_end,
                    "text": combined_text,
                })
            current_lines = []
            current_start = current_end

    if current_lines:
        combined_text = " ".join(current_lines).strip()
        if combined_text:
            sections.append({
                "start_seconds": current_start,
                "end_seconds": current_end,
                "text": combined_text,
            })

    return sections
