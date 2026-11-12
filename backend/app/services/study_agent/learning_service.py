from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import StudentLearningProfile, StudentTopicKnowledge, UserProfile
from app.services.study_agent.schemas import KnowledgeUpdateEvidence

logger = logging.getLogger(__name__)

# Valid evidence types that justify updating mastery
VALID_MASTERY_EVIDENCE_TYPES = {
    "student_solved_problem",
    "student_correct_quiz",
    "student_articulated_explanation",
    "student_self_assessed_mastery",
}

# Misconception evidence types
MISCONCEPTION_EVIDENCE_TYPES = {
    "student_incorrect_quiz",
    "student_misconception_demonstrated",
    "student_confusion_expressed",
}


def get_or_create_learning_profile(
    student_id: UUID,
    db: Session,
) -> StudentLearningProfile:
    """Retrieve existing learning profile or create a default one for the student."""
    profile = db.get(StudentLearningProfile, student_id)
    if profile is None:
        user = db.get(UserProfile, student_id)
        skill = user.skill_level if user else 1
        depth = "concise" if skill <= 2 else ("deep_12_step" if skill >= 7 else "balanced")
        profile = StudentLearningProfile(
            student_id=student_id,
            learning_style="balanced",
            explanation_depth=depth,
            preferred_language="ar",
            visual_preference=True,
            total_study_minutes=0,
            sessions_count=0,
        )
        db.add(profile)
        db.flush()
    return profile


def get_topic_knowledge_state(
    student_id: UUID,
    subject_id: UUID,
    topic_name: str,
    db: Session,
) -> StudentTopicKnowledge | None:
    """Retrieve knowledge state for a specific topic within a subject."""
    clean_topic = topic_name.strip().lower()
    return db.scalar(
        select(StudentTopicKnowledge).where(
            StudentTopicKnowledge.student_id == student_id,
            StudentTopicKnowledge.subject_id == subject_id,
            StudentTopicKnowledge.topic_name.ilike(clean_topic),
        )
    )


def record_student_learning_evidence(
    *,
    student_id: UUID,
    subject_id: UUID,
    topic_name: str,
    evidence_type: str,
    db: Session,
    understood_concept: str | None = None,
    misconception: str | None = None,
    delta_mastery: int = 0,
    notes: str = "",
) -> KnowledgeUpdateEvidence:
    """Evidence-based knowledge state update.
    
    IMPORTANT: An AI explanation does NOT constitute evidence of student mastery.
    Mastery updates only occur when evidence is provided of student comprehension
    or successful problem solving.
    """
    clean_topic = topic_name.strip()
    knowledge = get_topic_knowledge_state(student_id, subject_id, clean_topic, db)

    now = datetime.now(timezone.utc)
    is_new = False
    if knowledge is None:
        is_new = True
        knowledge = StudentTopicKnowledge(
            id=uuid4(),
            student_id=student_id,
            subject_id=subject_id,
            topic_name=clean_topic,
            mastery_score=0,
            confidence_score=0,
            understood_concepts=[],
            misconceptions=[],
            last_evidence_type=evidence_type,
            interaction_count=1,
            last_evaluated_at=now,
        )
        db.add(knowledge)
        db.flush()

    actual_delta_mastery = 0
    actual_delta_conf = 0
    new_understood = []
    new_misconceptions = []

    # Check evidence validity
    if evidence_type in VALID_MASTERY_EVIDENCE_TYPES:
        # Increase mastery
        increment = max(5, delta_mastery if delta_mastery > 0 else 10)
        knowledge.mastery_score = min(100, knowledge.mastery_score + increment)
        knowledge.confidence_score = min(100, knowledge.confidence_score + 10)
        actual_delta_mastery = increment
        actual_delta_conf = 10
        if understood_concept:
            curr_understood = list(knowledge.understood_concepts or [])
            if understood_concept not in curr_understood:
                curr_understood.append(understood_concept)
                knowledge.understood_concepts = curr_understood
                new_understood.append(understood_concept)
        knowledge.recommended_action = "Review advanced concepts or practice mixed problem sets."
    elif evidence_type in MISCONCEPTION_EVIDENCE_TYPES:
        # Record misconception and adjust confidence
        knowledge.confidence_score = max(0, knowledge.confidence_score - 10)
        actual_delta_conf = -10
        if misconception:
            curr_misc = list(knowledge.misconceptions or [])
            if misconception not in curr_misc:
                curr_misc.append(misconception)
                knowledge.misconceptions = curr_misc
                new_misconceptions.append(misconception)
        knowledge.recommended_action = f"Focus on clarifying: {misconception or 'foundational principles'}"
    else:
        # E.g. "ai_explanation_delivered" or "passive_reading"
        # Increment interaction count without falsely claiming student mastery
        knowledge.interaction_count = (knowledge.interaction_count or 0) + 1
        logger.info(
            "Recorded passive interaction for student %s on topic %s (no mastery change)",
            student_id,
            clean_topic,
        )

    knowledge.last_evidence_type = evidence_type
    knowledge.last_evaluated_at = now
    if not is_new:
        knowledge.interaction_count = (knowledge.interaction_count or 0) + 1

    return KnowledgeUpdateEvidence(
        evidence_type=evidence_type,
        topic_name=clean_topic,
        delta_mastery=actual_delta_mastery,
        delta_confidence=actual_delta_conf,
        new_understood_concepts=new_understood,
        new_misconceptions=new_misconceptions,
        notes=notes,
    )


def list_recent_weak_areas(
    student_id: UUID,
    subject_id: UUID,
    db: Session,
    limit: int = 5,
) -> list[str]:
    """List topics or concepts where the student has recorded misconceptions or low mastery."""
    rows = db.scalars(
        select(StudentTopicKnowledge)
        .where(
            StudentTopicKnowledge.student_id == student_id,
            StudentTopicKnowledge.subject_id == subject_id,
        )
        .order_by(StudentTopicKnowledge.mastery_score.asc())
        .limit(limit)
    ).all()

    weak_areas = []
    for r in rows:
        if r.misconceptions:
            for m in r.misconceptions:
                weak_areas.append(f"{r.topic_name}: {m}")
        elif r.mastery_score < 50:
            weak_areas.append(f"{r.topic_name} (إتقان {r.mastery_score}%)")
    return weak_areas[:limit]
