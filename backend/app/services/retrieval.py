import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any
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
    start_seconds: float | None = None
    end_seconds: float | None = None
    timestamp_url: str | None = None
    visual_description: str | None = None


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
        .join(YouTubeLink, YouTubeLink.id == YouTubeChunk.youtube_link_id)
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
                start_sec = getattr(chunk, "start_seconds", None)
                end_sec = getattr(chunk, "end_seconds", None)
                ts_url = f"https://www.youtube.com/watch?v={source.video_id}&t={int(start_sec)}s" if start_sec is not None else None
                vis_desc = getattr(chunk, "visual_description", None)
                ranked.append(
                    RetrievedPassage(
                        resource_id=source.id,
                        file_name=f"YouTube: {source.title or source.video_id}",
                        page_number=None,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        score=score,
                        start_seconds=start_sec,
                        end_seconds=end_sec,
                        timestamp_url=ts_url,
                        visual_description=vis_desc,
                    )
                )
    ranked.sort(key=lambda passage: (-passage.score, passage.file_name, passage.chunk_index))
    return ranked[: max(1, min(limit, 8))]


def sample_for_subject(db: Session, *, subject_id: UUID, limit: int = 4) -> list[RetrievedPassage]:
    """Sample resource chunks for quiz/flashcard generation."""
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
    if len(selected) < limit:
        transcript_rows = db.execute(
            select(Resource)
            .where(
                Resource.subject_id == subject_id,
                Resource.transcript_text.isnot(None),
                Resource.processing_status.in_(("ready", "truncated")),
            )
        ).scalars().all()
        for resource in transcript_rows:
            if resource.id not in seen_resources:
                selected.append(
                    (
                        type("Chunk", (), {"content": resource.transcript_text, "chunk_index": 0, "page_number": None})(),
                        resource,
                    )
                )
                seen_resources.add(resource.id)
                if len(selected) >= limit:
                    break
    if len(selected) < limit:
        yt_rows = db.execute(
            select(YouTubeChunk, YouTubeLink)
            .join(YouTubeLink, YouTubeLink.id == YouTubeChunk.youtube_link_id)
            .where(YouTubeLink.subject_id == subject_id, YouTubeLink.processing_status == "ready")
            .order_by(YouTubeChunk.chunk_index)
        ).all()
        for chunk, yt_link in yt_rows:
            selected.append((chunk, yt_link))
            if len(selected) >= limit:
                break

    passages: list[RetrievedPassage] = []
    for chunk, source in selected[: max(1, min(limit, 8))]:
        if isinstance(source, Resource):
            passages.append(
                RetrievedPassage(
                    resource_id=source.id,
                    file_name=source.file_name,
                    page_number=getattr(chunk, "page_number", None),
                    chunk_index=getattr(chunk, "chunk_index", 0),
                    content=chunk.content,
                    score=1.0,
                )
            )
        elif isinstance(source, YouTubeLink):
            passages.append(
                RetrievedPassage(
                    resource_id=source.id,
                    file_name=f"فيديو: {source.title or source.video_id}",
                    page_number=None,
                    chunk_index=getattr(chunk, "chunk_index", 0),
                    content=chunk.content,
                    score=1.0,
                )
            )
    return passages


def retrieve_concept_and_prerequisites(
    db: Session,
    *,
    subject_id: UUID,
    query: str,
    limit: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """Retrieve matched concepts, their definitions, and connected prerequisites from the knowledge graph."""
    from app.db.models import ConceptRelationship, ExtractedConcept
    from app.services.knowledge_ingestion.schemas import RelationshipType

    query_tokens = tokenize(query)
    if not query_tokens:
        return {"concepts": [], "prerequisites": [], "conflicts": []}

    all_concepts = db.scalars(
        select(ExtractedConcept).where(ExtractedConcept.subject_id == subject_id)
    ).all()

    matched: list[tuple[float, ExtractedConcept]] = []
    for c in all_concepts:
        c_tokens = set(tokenize(f"{c.name} {c.definition}"))
        overlap = len(set(query_tokens) & c_tokens)
        if overlap > 0:
            matched.append((float(overlap), c))

    matched.sort(key=lambda x: -x[0])
    selected_concepts = [c for _, c in matched[:limit]]

    concepts_data = [
        {
            "id": str(c.id),
            "name": c.name,
            "definition": c.definition,
            "type": c.concept_type,
            "page": c.page_or_slide_number,
            "source_excerpt": c.source_excerpt,
        }
        for c in selected_concepts
    ]

    prereqs_data: list[dict[str, Any]] = []
    conflicts_data: list[dict[str, Any]] = []
    seen_prereq_ids = set()

    for c in selected_concepts:
        # Find prerequisites
        p_rels = db.scalars(
            select(ConceptRelationship).where(
                ConceptRelationship.subject_id == subject_id,
                ConceptRelationship.target_concept_id == c.id,
                ConceptRelationship.relationship_type.in_((
                    RelationshipType.PREREQUISITE_OF.value,
                    RelationshipType.DEPENDS_ON.value,
                )),
            )
        ).all()
        for rel in p_rels:
            if rel.source_concept_id not in seen_prereq_ids:
                seen_prereq_ids.add(rel.source_concept_id)
                source_c = db.get(ExtractedConcept, rel.source_concept_id)
                if source_c:
                    prereqs_data.append({
                        "name": source_c.name,
                        "definition": source_c.definition,
                        "required_for": c.name,
                        "description": rel.description,
                    })

        # Check for recorded conflicts / contradictions
        c_rels = db.scalars(
            select(ConceptRelationship).where(
                ConceptRelationship.subject_id == subject_id,
                ConceptRelationship.source_concept_id == c.id,
                ConceptRelationship.relationship_type == RelationshipType.POTENTIALLY_CONFLICTS_WITH.value,
            )
        ).all()
        for rel in c_rels:
            conflicts_data.append({
                "concept_name": c.name,
                "conflict_details": rel.conflict_details or rel.description,
            })

    return {
        "concepts": concepts_data,
        "prerequisites": prereqs_data,
        "conflicts": conflicts_data,
    }

