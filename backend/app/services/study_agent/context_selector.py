from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.retrieval import RetrievedPassage

logger = logging.getLogger(__name__)

_MAX_BUDGET_CHARS = 24_000


class DynamicContextSelector:
    """Intelligent context selection engine separating conversation, student state, and RAG."""

    def __init__(self, budget_chars: int = _MAX_BUDGET_CHARS):
        self.budget_chars = budget_chars

    def assemble_context(
        self,
        *,
        subject_title: str,
        student_profile: dict[str, Any],
        passages: list[dict[str, Any]] | list[RetrievedPassage],
        conversation_history: list[dict[str, str]] | None = None,
        subject_overview: dict[str, Any] | None = None,
        topic_knowledge: dict[str, Any] | None = None,
        academic_chapters: list[dict[str, Any]] | None = None,
        missing_chapters: list[int] | None = None,
        prerequisites: list[dict[str, Any]] | None = None,
        cross_doc_conflicts: list[dict[str, Any]] | None = None,
    ) -> str:
        """Assemble structured, budget-managed context for the LLM."""
        remaining_budget = self.budget_chars
        sections: list[str] = []

        # 1. Subject Header
        sections.append(f"# المادة الدراسية: «{subject_title}»")

        # 1.1 Course Chapters & Logical Academic Structure
        if academic_chapters:
            ch_lines = []
            for ch in academic_chapters:
                ch_num = ch.get("chapter_number")
                ch_title = ch.get("title")
                ch_docs = "، ".join(f"«{d}»" for d in ch.get("documents", []))
                ch_lines.append(f"- **الفصل {ch_num}**: {ch_title} (الملفات: {ch_docs})")
            if missing_chapters:
                ch_lines.append(f"- ⚠️ **فصول غير متوفرة بعد في المكتبة**: الفصل {', '.join(str(m) for m in missing_chapters)}")
            sec_ch = "## الهيكل الأكاديمي المنظم للمقرر:\n" + "\n".join(ch_lines)
            sections.append(sec_ch)
            remaining_budget -= len(sec_ch)

        # 1.2 Prerequisite Concepts (Cross-Document Knowledge Graph)
        if prerequisites:
            prereq_lines = []
            for p in prerequisites:
                prereq_lines.append(
                    f"- **{p.get('name')}** (أساس مطلوب لـ: {p.get('required_for')}): {p.get('definition')}"
                )
            sec_prereq = "## المفاهيم التأسيسية السابقة من الفصول السابقة (Prerequisites):\n" + "\n".join(prereq_lines)
            sections.append(sec_prereq)
            remaining_budget -= len(sec_prereq)

        # 1.3 Cross-Document Discrepancy Warnings (if any)
        if cross_doc_conflicts:
            conf_lines = []
            for cf in cross_doc_conflicts:
                conf_lines.append(f"- ⚠️ {cf.get('conflict_details') or cf.get('description')}")
            sec_conf = "## تنبيه على اختلافات بين مراجع المادة:\n" + "\n".join(conf_lines)
            sections.append(sec_conf)
            remaining_budget -= len(sec_conf)

        # 2. Student Learning Profile & Cognitive State
        profile_parts = []
        if student_profile:
            skill = student_profile.get("skill_level", 1)
            style = student_profile.get("learning_style", "balanced")
            depth = student_profile.get("explanation_depth", "balanced")
            weak = student_profile.get("weak_areas", [])
            profile_parts.append(
                f"- مستوى الطالب التراكمي: {skill}/10 | أسلوب التعلم المفضل: {style} | عمق الشرح المطلوب: {depth}"
            )
            if weak:
                profile_parts.append(f"- مواضيع تحتاج تركيز وعناية خاصة: {', '.join(weak)}")

        if topic_knowledge and topic_knowledge.get("tracked"):
            m_score = topic_knowledge.get("mastery_score", 0)
            misc = topic_knowledge.get("misconceptions", [])
            und = topic_knowledge.get("understood_concepts", [])
            profile_parts.append(
                f"- إتقان الطالب لموضوع «{topic_knowledge.get('topic_name')}»: {m_score}%"
            )
            if misc:
                profile_parts.append(f"- المفاهيم الخاطئة المسجلة سابقاً: {', '.join(misc)}")
            if und:
                profile_parts.append(f"- المفاهيم المستوعبة بنجاح: {', '.join(und)}")

        if profile_parts:
            sec_prof = "## ملف الطالب المعرفي وسجل التعلم:\n" + "\n".join(profile_parts)
            sections.append(sec_prof)
            remaining_budget -= len(sec_prof)

        # 3. Conversation Continuity (recent turns)
        if conversation_history:
            history_lines = []
            for msg in conversation_history[-4:]:
                role_label = "الطالب" if msg.get("role") == "user" else "المعلم الذكي"
                history_lines.append(f"- **{role_label}**: {msg.get('content', '').strip()}")
            sec_hist = "## سياق المحادثة المباشرة الجارية:\n" + "\n".join(history_lines)
            sections.append(sec_hist)
            remaining_budget -= len(sec_hist)

        # 4. Available Course Materials Inventory
        if subject_overview:
            docs = subject_overview.get("documents", [])
            vids = subject_overview.get("videos", [])
            inv_lines = []
            if docs:
                file_names = "، ".join(f"«{d.get('file_name')}»" for d in docs[:8])
                inv_lines.append(f"- المراجع المرفوعة بمكتبة المادة ({len(docs)} ملف): {file_names}")
            if vids:
                vid_titles = "، ".join(f"«{v.get('title')}»" for v in vids[:5])
                inv_lines.append(f"- محاضرات الفيديو المتاحة ({len(vids)} محاضرة): {vid_titles}")
            if inv_lines:
                sec_inv = "## فهرس مراجع المادة المتاحة:\n" + "\n".join(inv_lines)
                sections.append(sec_inv)
                remaining_budget -= len(sec_inv)

        # 5. Grounded RAG Knowledge Passages (Attributed with S1, S2...)
        if passages and remaining_budget > 1000:
            passage_blocks = []
            for idx, p in enumerate(passages, start=1):
                if isinstance(p, dict):
                    fname = p.get("file_name", "مرجع")
                    page = f"، صفحة {p.get('page_number')}" if p.get("page_number") is not None else ""
                    content = p.get("content", "")
                else:
                    fname = p.file_name
                    page = f"، صفحة {p.page_number}" if p.page_number is not None else ""
                    content = p.content

                block = (
                    f"### [S{idx}] ملف: {fname}{page}\n"
                    f"```text\n{content.strip()}\n```"
                )
                if len(block) > remaining_budget:
                    block = block[:remaining_budget] + "\n```"
                passage_blocks.append(block)
                remaining_budget -= len(block)
                if remaining_budget <= 200:
                    break

            if passage_blocks:
                sec_passages = "## المقاطع النصية المسترجعة من مراجع المادة المعتمدة:\n" + "\n\n".join(passage_blocks)
                sections.append(sec_passages)
        elif not passages:
            sections.append("## مراجع المادة:\n(لا توجد مقاطع نصية مسترجعة لهذا السؤال تحديداً)")

        return "\n\n".join(sections)
