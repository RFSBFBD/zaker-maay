from __future__ import annotations

import logging
import re
from typing import Any

from app.services.knowledge_ingestion.schemas import (
    AcademicUnderstandingResult,
    CanonicalMarkdownDocument,
    ExtractedConceptItem,
)

logger = logging.getLogger(__name__)

# Concept detection heuristics
_DEFINITION_PATTERNS = [
    r"(?:is defined as|refers to|means|is known as)\s+([^.\n]+)",
    r"(?:يُعرف بـ|يُقصد بـ|هو عبارة عن|هو نظام|هي عملية)\s+([^.\n]+)",
]

_PREREQUISITE_TRIGGERS = [
    r"(?:prerequisite|requires prior knowledge of|builds upon|as seen in chapter|كما رأينا في)\s+([^.\n]+)",
]


def analyze_academic_document(
    canonical_doc: CanonicalMarkdownDocument,
    subject_title: str = "",
) -> AcademicUnderstandingResult:
    """Analyze canonical markdown document, extracting concepts, definitions, and academic structure."""
    text = canonical_doc.markdown_content
    lines = text.split("\n")

    # 1. Detect concepts, definitions, and source excerpts
    extracted_concepts: list[ExtractedConceptItem] = []
    seen_concept_names: set[str] = set()

    current_page = canonical_doc.chapter_number or 1

    for line_idx, line in enumerate(lines):
        line_clean = line.strip()

        # Update page tracking from canonical markdown headings
        page_match = re.search(r"## صفحة / شريحة (\d+)", line_clean)
        if page_match:
            try:
                current_page = int(page_match.group(1))
            except ValueError:
                pass

        # Look for explicit section headers indicating concepts (### Routing, ### Algorithm, etc.)
        if line_clean.startswith("### "):
            candidate_name = line_clean.replace("### ", "").strip()
            # Skip generic headings
            if candidate_name.lower() in ("introduction", "definitions", "processes", "examples", "المقدمة", "التعريفات"):
                continue

            # Look ahead for definition or explanation
            definition_snippet = ""
            for next_idx in range(line_idx + 1, min(line_idx + 6, len(lines))):
                next_line = lines[next_idx].strip()
                if next_line and not next_line.startswith("#") and not next_line.startswith("---"):
                    definition_snippet = next_line
                    break

            if candidate_name and candidate_name.lower() not in seen_concept_names:
                seen_concept_names.add(candidate_name.lower())
                c_type = "concept"
                if "algorithm" in candidate_name.lower() or "خوارزمية" in candidate_name:
                    c_type = "algorithm"
                elif "process" in candidate_name.lower() or "عملية" in candidate_name:
                    c_type = "process"
                elif "protocol" in candidate_name.lower() or "بروتوكول" in candidate_name:
                    c_type = "protocol"

                extracted_concepts.append(
                    ExtractedConceptItem(
                        name=candidate_name,
                        definition=definition_snippet or f"مفهوم أكاديمي مشروح في صفحة {current_page}.",
                        concept_type=c_type,
                        page_or_slide_number=current_page,
                        source_excerpt=definition_snippet[:300] if definition_snippet else candidate_name,
                        confidence_score=0.95,
                    )
                )

        # Look for in-text definition patterns
        for pat in _DEFINITION_PATTERNS:
            match = re.search(pat, line_clean, re.IGNORECASE)
            if match:
                prefix = line_clean[:match.start()].strip()
                words = prefix.split()
                if 1 <= len(words) <= 5:
                    c_name = " ".join(words[-3:]).strip(": -*#")
                    if c_name and len(c_name) > 2 and c_name.lower() not in seen_concept_names:
                        seen_concept_names.add(c_name.lower())
                        extracted_concepts.append(
                            ExtractedConceptItem(
                                name=c_name,
                                definition=match.group(0)[:250].strip(),
                                concept_type="definition",
                                page_or_slide_number=current_page,
                                source_excerpt=line_clean[:300],
                                confidence_score=0.9,
                            )
                        )

    # 2. Prerequisites identification
    prerequisites = []
    for pat in _PREREQUISITE_TRIGGERS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            prereq_phrase = m.group(1).strip()
            if len(prereq_phrase) > 2 and prereq_phrase not in prerequisites:
                prerequisites.append(prereq_phrase[:100])

    # 3. Learning objectives inference
    learning_objectives = []
    for line in lines[:60]:
        if any(keyword in line.lower() for keyword in ["objective", "goal", "الأهداف", "مخرجات التعلم", "يتوقع من الطالب"]):
            clean_obj = line.strip("*- #").strip()
            if len(clean_obj) > 8:
                learning_objectives.append(clean_obj)

    # Fallback to topic-based objectives if none explicitly stated
    if not learning_objectives and extracted_concepts:
        top_concepts = [c.name for c in extracted_concepts[:3]]
        learning_objectives.append(f"فهم الأسس النظرية والتطبيقية لـ: {', '.join(top_concepts)}")

    # 4. Extract structured topics
    topics = []
    for h in canonical_doc.outline:
        if h.startswith("### "):
            t_title = h.replace("### ", "").strip()
            topics.append({
                "title": t_title,
                "summary": f"موضوع دراسي ضمن {canonical_doc.title}",
                "is_foundational": any(k in t_title.lower() for k in ["intro", "basic", "fundamental", "أساس", "مقدمة"]),
            })

    # 5. Document summary
    first_paras = [l for l in lines[:30] if l and not l.startswith("#") and not l.startswith(">") and not l.startswith("-")]
    summary = " ".join(first_paras[:2])[:400] if first_paras else f"وثيقة معرفية تعليمية لموضوع {canonical_doc.title}"

    return AcademicUnderstandingResult(
        subject_title=subject_title,
        detected_course=subject_title,
        detected_chapter_number=canonical_doc.chapter_number,
        detected_chapter_title=canonical_doc.title,
        summary=summary,
        learning_objectives=learning_objectives[:5],
        topics=topics[:12],
        concepts=extracted_concepts[:25],
        prerequisites=prerequisites[:5],
        identified_misconceptions=[],
        academic_level="undergraduate",
    )
