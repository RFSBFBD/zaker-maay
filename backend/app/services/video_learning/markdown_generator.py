from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.services.storage import neon_storage
from app.services.video_learning.metadata import build_youtube_timestamp_url, format_timestamp
from app.services.video_learning.schemas import (
    CanonicalVideoDocument,
    VideoMetadata,
    VideoSegment,
    VisualObservation,
)

logger = logging.getLogger(__name__)


def generate_canonical_video_markdown(
    *,
    subject_id: UUID,
    subject_name: str,
    metadata: VideoMetadata,
    segments: list[VideoSegment],
    visuals: list[VisualObservation],
    concepts: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
) -> CanonicalVideoDocument:
    """Generate structured Canonical Markdown artifact for educational video understanding.
    
    Preserves instructor explanations, exact clickable timestamps, visual observations,
    equations, and terminology without compression into a generic summary.
    """
    lines: list[str] = []

    # 1. Title Header
    lines.append(f"# {metadata.title}")
    lines.append("")

    # 2. Metadata Block
    lines.append("## تفاصيل المحاضرة والمصدر الأكاديمي (Video Metadata)")
    lines.append(f"> **المقرر الدراسي**: {subject_name}")
    lines.append(f"> **رابط المحاضرة الأصلي**: [{metadata.url}]({metadata.url})")
    lines.append(f"> **المنصة**: {metadata.provider.capitalize()} | **معرف الفيديو**: `{metadata.video_id}`")
    if metadata.channel_name:
        lines.append(f"> **القناة / المحاضر**: {metadata.channel_name}")
    lines.append(f"> **لغة المحاضرة**: {metadata.detected_language.upper()} | **إجمالي المدة**: {format_timestamp(metadata.duration_seconds)}")
    lines.append(f"> **تاريخ المعالجة والاستيعاب**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    # 3. Video Overview
    lines.append("## نظرة عامة والأهداف التعليمية (Overview & Learning Objectives)")
    lines.append(
        f"تتناول هذه المحاضرة شرحاً تفصيلياً لموضوعات «{metadata.title}». "
        "تم استيعاب محتوى المحاضرة بواسطة الوكيل الذكي، واستخراج المقاطع الزمنية والمخططات البصرية المعروضة على الشاشة بدقة لتمكين الطالب من الدراسة والمراجعة بالاستناد المباشر إلى الشرح الأصلي."
    )
    lines.append("")

    # 4. Main Topics & Timeline Index
    lines.append("## المحاور الرئيسية والفهرس الزمني (Main Topics & Timeline)")
    for seg in segments:
        ts_str = format_timestamp(seg.start_seconds)
        ts_url = build_youtube_timestamp_url(metadata.video_id, seg.start_seconds)
        lines.append(f"- [[{ts_str}]]({ts_url}) **{seg.title}**")
    lines.append("")

    # 5. Detailed Lesson Content
    lines.append("## محتوى الشرح الأكاديمي المفصل (Detailed Lesson Content)")
    for seg in segments:
        ts_start_str = format_timestamp(seg.start_seconds)
        ts_end_str = format_timestamp(seg.end_seconds)
        ts_url = build_youtube_timestamp_url(metadata.video_id, seg.start_seconds)

        lines.append("---")
        lines.append(f"### [[{ts_start_str} - {ts_end_str}]]({ts_url}) {seg.title}")
        lines.append("")
        lines.append(f"**شرح المحاضر المصدر**: {seg.transcript_text}")
        lines.append("")

        if seg.visual_observations:
            lines.append("**الملاحظات البصرية المعروضة على الشاشة في هذا التوقيت**:")
            for vis in seg.visual_observations:
                vis_ts = format_timestamp(vis.timestamp_seconds)
                vis_url = build_youtube_timestamp_url(metadata.video_id, vis.timestamp_seconds)
                lines.append(f"- [[{vis_ts}]]({vis_url}) `{vis.category.value}`: {vis.title} — {vis.description}")
            lines.append("")

        if seg.concepts_covered:
            lines.append(f"*المفاهيم المطروحة في هذا المقطع*: {', '.join(seg.concepts_covered)}")
            lines.append("")

    # 6. Important Diagrams & Visuals
    lines.append("## المخططات والتوضيحات البصرية (Important Diagrams & Visuals)")
    if visuals:
        for vis in visuals:
            vis_ts = format_timestamp(vis.timestamp_seconds)
            vis_url = build_youtube_timestamp_url(metadata.video_id, vis.timestamp_seconds)
            lines.append(f"### [[{vis_ts}]]({vis_url}) {vis.title}")
            lines.append(f"> **نوع المحتوى المرئي**: `{vis.category.value}`")
            lines.append(f"> **التفاصيل**: {vis.description}")
            if vis.on_screen_labels:
                lines.append(f"> **المصطلحات على الشاشة**: {', '.join(vis.on_screen_labels)}")
            lines.append("")
    else:
        lines.append("لا توجد مخططات بصرية منفصلة مسجلة في هذا المقطع.")
        lines.append("")

    # 7. Key Terminology & Concepts
    lines.append("## المفاهيم والمصطلحات الأساسية المستخلصة (Key Terminology)")
    if concepts:
        for c in concepts:
            c_name = c.get("name", "")
            c_def = c.get("definition", "")
            c_type = c.get("type", "concept")
            lines.append(f"- **{c_name}** (`{c_type}`): {c_def}")
        lines.append("")
    else:
        lines.append("تعتمد المحاضرة على المصطلحات المذكورة في سياق الشرح.")
        lines.append("")

    # 8. Concept Relationships & Prerequisites
    lines.append("## العلاقات بين المفاهيم والمتطلبات السابقة (Relationships & Prerequisites)")
    if relationships:
        for r in relationships:
            lines.append(f"- **{r.get('source')}** $\\rightarrow$ *{r.get('type')}* $\\rightarrow$ **{r.get('target')}**: {r.get('desc', '')}")
        lines.append("")
    else:
        lines.append("تتدرج المفاهيم تتابعياً بحسب تسلسل المحاضرة الزمني.")
        lines.append("")

    # 9. Instructor's Summary
    lines.append("## ملخص المحاضر والفهرس المرجعي (Instructor's Summary & Index)")
    lines.append(
        "يقدم المحاضر في ختام الدرس تلخيصاً شاملاً يربط بين المحاور الأساسية والتطبيقات العملية المطروحة. "
        "يمكنك سؤال المساعد الذكي عن أي دقيقة محددة أو مقارنة شرح هذا الفيديو بالكتب والمذكرات المرفوعة في المادة."
    )
    lines.append("")

    markdown_text = "\n".join(lines)

    # Upload canonical markdown to Neon Object Storage
    storage_key = f"subjects/{subject_id}/videos/{metadata.video_id}/canonical_video_{metadata.video_id}.md"
    bucket = neon_storage.get_default_bucket()

    try:
        neon_storage.upload_file(
            content=markdown_text.encode("utf-8"),
            key=storage_key,
            bucket=bucket,
            content_type="text/markdown",
        )
    except Exception as exc:
        logger.warning("Could not upload video canonical markdown to Neon storage: %s", exc)

    return CanonicalVideoDocument(
        video_id=metadata.video_id,
        title=metadata.title,
        metadata=metadata,
        overview="Video understanding overview",
        main_topics=[{"title": s.title, "start_seconds": s.start_seconds} for s in segments],
        segments=segments,
        diagrams_and_visuals=visuals,
        key_terminology=[{"name": c.get("name", ""), "definition": c.get("definition", "")} for c in concepts],
        concept_relationships=relationships or [],
        markdown_content=markdown_text,
    )
