import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Resource, ResourceChunk, YouTubeChunk, YouTubeLink

ARABIC_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670\u0640]")
TOKEN_PATTERN = re.compile(r"[a-z0-9\u0600-\u06ff]+")
STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "what", "when", "where", "which", "how",
    "ما", "ماذا", "متى", "أين", "كيف", "هل", "في", "من", "عن", "على", "إلى", "هو", "هي", "هذا", "هذه",
}


@dataclass(frozen=True)
class RetrievedPassage:
    resource_id: UUID
    file_name: str
    page_number: int | None
    chunk_index: int
    content: str
    score: float


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = ARABIC_DIACRITICS.sub("", normalized).translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
    return [token for token in TOKEN_PATTERN.findall(normalized) if token not in STOP_WORDS and len(token) > 1]


def retrieve_for_subject(db: Session, *, subject_id: UUID, query: str, limit: int = 4) -> list[RetrievedPassage]:
    query_terms = set(tokenize(query))
    if not query_terms:
        return []
    rows = db.execute(
        select(ResourceChunk, Resource)
        .join(Resource, Resource.id == ResourceChunk.resource_id)
        .where(Resource.subject_id == subject_id, Resource.processing_status.in_(("ready", "truncated")))
    ).all()
    resource_documents = [(chunk, resource, tokenize(chunk.content)) for chunk, resource in rows]
    yt_rows = db.execute(
        select(YouTubeChunk, YouTubeLink)
        .where(YouTubeLink.subject_id == subject_id, YouTubeLink.processing_status == "ready")
    ).all()
    yt_documents = [(chunk, yt_link, tokenize(chunk.content)) for chunk, yt_link in yt_rows]
    all_documents = resource_documents + yt_documents
    if not all_documents:
        return []
    document_frequency: Counter[str] = Counter()
    for _, _, tokens in all_documents:
        document_frequency.update(set(tokens) & query_terms)
    average_length = max(1.0, sum(len(tokens) for _, _, tokens in all_documents) / len(all_documents))
    ranked: list[RetrievedPassage] = []
    for chunk, source, tokens in all_documents:
        frequencies = Counter(tokens)
        length = len(tokens)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse_frequency = math.log1p((len(all_documents) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
            denominator = frequency + 1.2 * (0.25 + 0.75 * length / average_length)
            score += inverse_frequency * (frequency * 2.2 / denominator)
        if score > 0:
            if isinstance(source, Resource):
                ranked.append(
                    RetrievedPassage(
                        resource_id=source.id,
                        file_name=source.file_name,
                        page_number=chunk.page_number,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        score=score,
                    )
                )
            elif isinstance(source, YouTubeLink):
                ranked.append(
                    RetrievedPassage(
                        resource_id=source.id,
                        file_name=f"YouTube: {source.title or source.video_id}",
                        page_number=None,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        score=score,
                    )
                )
    ranked.sort(key=lambda passage: (-passage.score, passage.file_name, passage.chunk_index))
    return ranked[: max(1, min(limit, 8))]


def sample_for_subject(db: Session, *, subject_id: UUID, limit: int = 4) -> list[RetrievedPassage]:
    """Sample resource chunks only — used for quiz/flashcard generation.
    YouTube transcript chunks are intentionally excluded because quiz/study
    artifact generation stores source_resource_id pointing to Resource rows,
    and mixing in YouTubeLink IDs would violate that invariant.
    """
    rows = db.execute(
        select(ResourceChunk, Resource)
        .join(Resource, Resource.id == ResourceChunk.resource_id)
        .where(Resource.subject_id == subject_id, Resource.processing_status.in_(("ready", "truncated")))
        .order_by(Resource.created_at, Resource.file_name, ResourceChunk.chunk_index)
    ).all()
    selected: list[tuple[ResourceChunk, Resource]] = []
    seen_resources: set[UUID] = set()
    for chunk, resource in rows:
        if resource.id not in seen_resources:
            selected.append((chunk, resource))
            seen_resources.add(resource.id)
            if len(selected) == limit:
                break
    if len(selected) < limit:
        selected_ids = {chunk.id for chunk, _ in selected}
        for chunk, resource in rows:
            if chunk.id in selected_ids:
                continue
            selected.append((chunk, resource))
            selected_ids.add(chunk.id)
            if len(selected) >= limit:
                break
    return [
        RetrievedPassage(
            resource_id=resource.id,
            file_name=resource.file_name,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=1.0,
        )
        for chunk, resource in selected[: max(1, min(limit, 8))]
    ]
