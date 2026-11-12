from __future__ import annotations

import logging
from typing import Any

from app.services.adaptive_engine import (
    ContentArchetype,
    generate_adaptive_svg,
)
from app.services.study_agent.schemas import DisciplineDomain, VisualArtifact

logger = logging.getLogger(__name__)


def generate_educational_visual(
    topic: str,
    visual_type: str = "mindmap",
    discipline: DisciplineDomain = DisciplineDomain.GENERAL,
    context: str = "",
) -> VisualArtifact:
    """Generate structured educational visual artifact with clean, self-contained SVG."""
    clean_topic = topic.strip()
    archetype = ContentArchetype.CONCEPT
    if visual_type == "comparison":
        archetype = ContentArchetype.COMPARISON
    elif discipline == DisciplineDomain.COMPUTER_SCIENCE:
        archetype = ContentArchetype.PROGRAMMING
    elif discipline == DisciplineDomain.NATURAL_SCIENCES:
        archetype = ContentArchetype.PROCESS_SCIENCE

    svg_dict = generate_adaptive_svg(
        topic=clean_topic,
        archetype=archetype,
        context=context,
    )

    svg_content = svg_dict.get("svg", "")
    title = svg_dict.get("title", f"مخطط تعليمي: {clean_topic}")
    desc = svg_dict.get("description", f"تمثيل بصري مفاهيمي لموضوع «{clean_topic}».")

    return VisualArtifact(
        visual_type=visual_type,
        title=title,
        svg=svg_content,
        description=desc,
    )
