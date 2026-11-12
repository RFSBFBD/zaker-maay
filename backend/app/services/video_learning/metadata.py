from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlsplit

import requests

from app.services.video_learning.schemas import VideoMetadata

logger = logging.getLogger(__name__)

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def parse_youtube_video_id(raw_url: str) -> str:
    """Validate YouTube URL safely and extract the 11-character video ID, protecting against SSRF."""
    try:
        parsed = urlsplit(raw_url.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid YouTube URL.") from None

    if parsed.scheme != "https" or host not in ALLOWED_HOSTS or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError("Only secure YouTube video links (https://youtube.com or https://youtu.be) are supported.")

    segments = [part for part in parsed.path.split("/") if part]
    video_id = ""

    if host == "youtu.be" and len(segments) == 1:
        video_id = segments[0]
    elif host.endswith("youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif len(segments) >= 2 and segments[0] in {"embed", "shorts", "live"}:
            video_id = segments[1]

    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise ValueError("YouTube URL does not contain a valid 11-character video ID.")

    return video_id


def format_timestamp(seconds: float | int) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    sec = max(0, int(seconds))
    hrs = sec // 3600
    mins = (sec % 3600) // 60
    rem = sec % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{rem:02d}"
    return f"{mins:02d}:{rem:02d}"


def build_youtube_timestamp_url(video_id: str, seconds: float | int) -> str:
    """Build a clickable link to YouTube jumping to the specific timestamp."""
    sec_int = max(0, int(seconds))
    return f"https://www.youtube.com/watch?v={video_id}&t={sec_int}s"


def fetch_video_metadata(video_id: str) -> VideoMetadata:
    """Fetch video metadata via YouTube oEmbed API without requiring complex scraping."""
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    default_title = f"محاضرة مرئية ({video_id})"
    channel_name = None

    try:
        oembed_url = f"https://www.youtube.com/oembed?url={canonical_url}&format=json"
        resp = requests.get(oembed_url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            default_title = data.get("title", default_title)
            channel_name = data.get("author_name", channel_name)
    except Exception as exc:
        logger.warning("Could not fetch oEmbed metadata for video %s: %s", video_id, exc)

    return VideoMetadata(
        video_id=video_id,
        url=canonical_url,
        provider="youtube",
        title=default_title,
        channel_name=channel_name,
        duration_seconds=0,
    )
