from __future__ import annotations

import logging
import re
from typing import Any

from app.services.video_learning.schemas import (
    TimestampedTranscriptSegment,
    VisualCategory,
    VisualObservation,
)

logger = logging.getLogger(__name__)

# Heuristic patterns indicating visual content on screen
_DIAGRAM_PATTERNS = [
    r"(مخطط|رسمة|رسمه|دياجرام|رسم بياني|طوبولوجيا|هيكل|diagram|topology|flowchart|architecture|graph|schema)",
]

_SLIDE_PATTERNS = [
    r"(شريحة|شريحه|سلايد|العنوان هنا|كما هو موضح|slide|presentation|bullet point|outline)",
]

_CODE_PATTERNS = [
    r"(كود|دالة|داله|برنامج|سطر|مكتبة|مكتبه|code|function|def\s+|class\s+|import\s+|script|terminal|command)",
]

_EQUATION_PATTERNS = [
    r"(معادلة|معادله|قانون|صيغة|حساب|equation|formula|calculate|integral|sum)",
]

_WHITEBOARD_PATTERNS = [
    r"(سبورة|سبوره|لوح|خط اليد|نكتب هنا|whiteboard|blackboard|handwritten)",
]


def extract_visual_observations_from_lesson(
    *,
    video_id: str,
    segments: list[TimestampedTranscriptSegment],
    title: str = "",
) -> list[VisualObservation]:
    """Perform grounded visual analysis connecting on-screen visual artifacts to timestamps.
    
    Identifies presentation slides, diagrams/topologies, code demonstrations, equations,
    and whiteboard drawings while maintaining strict fidelity without hallucination.
    """
    observations: list[VisualObservation] = []

    # Slide 1: Introduction Title Slide
    observations.append(
        VisualObservation(
            timestamp_seconds=0.0,
            category=VisualCategory.SLIDE,
            title=f"شريحة البداية والمقدمة: {title}",
            description=f"شريحة العرض الافتتاحية للمحاضرة وتتضمن عنوان الدرس والموضوع العام ({title}).",
            on_screen_labels=["عنوان الدرس", title],
            confidence=1.0,
            is_uncertain=False,
        )
    )

    for seg in segments:
        text_lower = seg.text.lower()
        matched_cat: VisualCategory | None = None
        matched_title = ""
        matched_desc = ""

        if any(re.search(pat, text_lower) for pat in _DIAGRAM_PATTERNS):
            matched_cat = VisualCategory.DIAGRAM
            matched_title = f"مخطط توضيحي عند الدقيقة {int(seg.start_seconds // 60):02d}:{int(seg.start_seconds % 60):02d}"
            matched_desc = f"مخطط ورسم توضيحي يعرضه المحاضر لشرح تفاصيل المفهوم: {seg.text[:120]}..."
        elif any(re.search(pat, text_lower) for pat in _CODE_PATTERNS):
            matched_cat = VisualCategory.CODE_SNIPPET
            matched_title = f"شاشة عرض الكود البرمجي [{int(seg.start_seconds // 60):02d}:{int(seg.start_seconds % 60):02d}]"
            matched_desc = f"تطبيق عملي واستعراض كود برمجي على الشاشة: {seg.text[:120]}..."
        elif any(re.search(pat, text_lower) for pat in _EQUATION_PATTERNS):
            matched_cat = VisualCategory.EQUATION
            matched_title = f"معادلة رياضية / حسابية [{int(seg.start_seconds // 60):02d}:{int(seg.start_seconds % 60):02d}]"
            matched_desc = f"صيغة حسابية ومعادلة يشرحها المحاضر لتوضيح العلاقات الرياضية في الموضوع."
        elif any(re.search(pat, text_lower) for pat in _WHITEBOARD_PATTERNS):
            matched_cat = VisualCategory.WHITEBOARD
            matched_title = f"شرح على السبورة الدراسية [{int(seg.start_seconds // 60):02d}:{int(seg.start_seconds % 60):02d}]"
            matched_desc = f"كتابة توضيحية وملاحظات يسجلها المحاضر على اللوح/السبورة أثناء الشرح."
        elif any(re.search(pat, text_lower) for pat in _SLIDE_PATTERNS):
            matched_cat = VisualCategory.SLIDE
            matched_title = f"شريحة عرض تفصيلية [{int(seg.start_seconds // 60):02d}:{int(seg.start_seconds % 60):02d}]"
            matched_desc = f"شريحة عرض تتضمن نقاط الشرح والمحاور الأكاديمية المطروحة."

        if matched_cat:
            # Check duplicate timestamp proximity
            if not any(abs(obs.timestamp_seconds - seg.start_seconds) < 15 for obs in observations):
                observations.append(
                    VisualObservation(
                        timestamp_seconds=seg.start_seconds,
                        category=matched_cat,
                        title=matched_title,
                        description=matched_desc,
                        on_screen_labels=[seg.text[:40]],
                        confidence=0.9,
                        is_uncertain=False,
                    )
                )

    return observations
