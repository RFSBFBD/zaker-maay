from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import ConceptRelationship, ExtractedConcept, Resource
from app.services.knowledge_ingestion.schemas import (
    AcademicUnderstandingResult,
    RelationshipType,
)

logger = logging.getLogger(__name__)


def ingest_concepts_and_build_relationships(
    *,
    db: Session,
    subject_id: UUID,
    resource_id: UUID,
    understanding: AcademicUnderstandingResult,
) -> tuple[int, int]:
    """Persist extracted concepts and build cross-document relationships across the subject."""
    created_concepts_count = 0
    created_relationships_count = 0

    # 1. Persist extracted concepts
    persisted_concept_map: dict[str, ExtractedConcept] = {}

    for c_item in understanding.concepts:
        norm_name = c_item.name.strip().lower()

        # Check for existing concept in subject
        existing = db.scalar(
            select(ExtractedConcept).where(
                ExtractedConcept.subject_id == subject_id,
                ExtractedConcept.normalized_name == norm_name,
            )
        )

        if not existing:
            concept_record = ExtractedConcept(
                id=uuid4(),
                subject_id=subject_id,
                resource_id=resource_id,
                name=c_item.name.strip(),
                normalized_name=norm_name,
                definition=c_item.definition.strip(),
                concept_type=c_item.concept_type,
                page_or_slide_number=c_item.page_or_slide_number,
                source_excerpt=c_item.source_excerpt,
                confidence_score=c_item.confidence_score,
            )
            db.add(concept_record)
            created_concepts_count += 1
            persisted_concept_map[norm_name] = concept_record
        else:
            # Check for potential conflicts / contradictory definitions
            if (
                len(existing.definition) > 20
                and len(c_item.definition) > 20
                and existing.resource_id != resource_id
            ):
                _record_potential_conflict(
                    db=db,
                    subject_id=subject_id,
                    concept=existing,
                    new_resource_id=resource_id,
                    new_definition=c_item.definition,
                )
            persisted_concept_map[norm_name] = existing

    db.flush()

    # 2. Build cross-document semantic relationships
    all_subject_concepts = db.scalars(
        select(ExtractedConcept).where(ExtractedConcept.subject_id == subject_id)
    ).all()

    for current in list(persisted_concept_map.values()):
        c_text = f"{current.name} {current.definition}".lower()

        for other in all_subject_concepts:
            if other.id == current.id:
                continue

            other_name = other.name.lower()
            other_res_id = other.resource_id

            # Case A: Current concept explicitly references another concept
            if other_name in c_text and len(other_name) > 3:
                rel_type = (
                    RelationshipType.EXPANDS.value
                    if other_res_id != current.resource_id
                    else RelationshipType.REFERENCES.value
                )
                if _add_relationship_if_missing(
                    db=db,
                    subject_id=subject_id,
                    source_id=current.id,
                    target_id=other.id,
                    rel_type=rel_type,
                    description=f"مفهوم «{current.name}» يشير إلى أو يتوسع في «{other.name}».",
                ):
                    created_relationships_count += 1

            # Case B: Prerequisites inferred from understanding
            for prereq in understanding.prerequisites:
                if other_name in prereq.lower() or prereq.lower() in other_name:
                    if _add_relationship_if_missing(
                        db=db,
                        subject_id=subject_id,
                        source_id=other.id,
                        target_id=current.id,
                        rel_type=RelationshipType.PREREQUISITE_OF.value,
                        description=f"«{other.name}» يُعد متطلباً سابقاً لفهم «{current.name}».",
                    ):
                        created_relationships_count += 1

    db.flush()
    return created_concepts_count, created_relationships_count


def _record_potential_conflict(
    *,
    db: Session,
    subject_id: UUID,
    concept: ExtractedConcept,
    new_resource_id: UUID,
    new_definition: str,
) -> None:
    """Record potential contradiction between two documents without silently discarding either."""
    res_orig = db.get(Resource, concept.resource_id)
    res_new = db.get(Resource, new_resource_id)
    orig_fn = res_orig.file_name if res_orig else "المرجع الأول"
    new_fn = res_new.file_name if res_new else "المرجع الثاني"

    conflict_details = (
        f"اختلاف في صياغة أو تفسير المفهوم بين المراجع:\n"
        f"- في {orig_fn} (صفحة {concept.page_or_slide_number or '—'}): «{concept.definition}»\n"
        f"- في {new_fn}: «{new_definition}»"
    )

    # Add self-referential or relationship conflict note
    _add_relationship_if_missing(
        db=db,
        subject_id=subject_id,
        source_id=concept.id,
        target_id=concept.id,
        rel_type=RelationshipType.POTENTIALLY_CONFLICTS_WITH.value,
        description=f"يوجد تباين دلالي بين {orig_fn} و{new_fn}.",
        conflict_details=conflict_details,
    )


def _add_relationship_if_missing(
    *,
    db: Session,
    subject_id: UUID,
    source_id: UUID,
    target_id: UUID,
    rel_type: str,
    description: str,
    conflict_details: str | None = None,
) -> bool:
    """Safely insert a relationship avoiding duplicates."""
    existing = db.scalar(
        select(ConceptRelationship).where(
            ConceptRelationship.subject_id == subject_id,
            ConceptRelationship.source_concept_id == source_id,
            ConceptRelationship.target_concept_id == target_id,
            ConceptRelationship.relationship_type == rel_type,
        )
    )
    if not existing:
        rel = ConceptRelationship(
            id=uuid4(),
            subject_id=subject_id,
            source_concept_id=source_id,
            target_concept_id=target_id,
            relationship_type=rel_type,
            description=description,
            conflict_details=conflict_details,
            confidence_score=0.9,
        )
        db.add(rel)
        return True
    return False


def get_concept_prerequisites(
    db: Session,
    subject_id: UUID,
    concept_name: str,
) -> list[dict[str, Any]]:
    """Retrieve prerequisite concepts for a given concept within a subject."""
    norm = concept_name.strip().lower()
    concept = db.scalar(
        select(ExtractedConcept).where(
            ExtractedConcept.subject_id == subject_id,
            ExtractedConcept.normalized_name == norm,
        )
    )
    if not concept:
        return []

    prereq_rels = db.scalars(
        select(ConceptRelationship).where(
            ConceptRelationship.subject_id == subject_id,
            ConceptRelationship.target_concept_id == concept.id,
            ConceptRelationship.relationship_type == RelationshipType.PREREQUISITE_OF.value,
        )
    ).all()

    results = []
    for rel in prereq_rels:
        source_c = db.get(ExtractedConcept, rel.source_concept_id)
        if source_c:
            results.append({
                "concept_id": str(source_c.id),
                "name": source_c.name,
                "definition": source_c.definition,
                "resource_id": str(source_c.resource_id),
                "page": source_c.page_or_slide_number,
                "description": rel.description,
            })
    return results
