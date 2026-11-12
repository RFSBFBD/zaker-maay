from __future__ import annotations

import json
import logging
from typing import Any

from app.services.study_agent.schemas import SlideDeck, SlideItem

logger = logging.getLogger(__name__)


def generate_structured_slide_deck(
    topic: str,
    subject_title: str,
    context: str = "",
    target_slides_count: int = 5,
) -> SlideDeck:
    """Generate a clean, structured educational presentation deck."""
    clean_topic = topic.strip()
    slides = []

    # Slide 1: Title & Overview
    slides.append(
        SlideItem(
            slide_number=1,
            title=f"مقدمة تأصيلية: {clean_topic}",
            subtitle=f"مقرر: {subject_title}",
            bullet_points=[
                f"أهمية المفهوم في علوم وحوسبة {subject_title}",
                "الهدف التعليمي والمخرجات المستهدفة",
                "خارطة الطريق المفاهيمية للعرض",
            ],
            presenter_notes="ابدأ بالربط بين هذا المفهوم والتطبيقات العملية المباشرة لتحفيز انتباه الطلاب.",
            visual_suggestion="خريطة ذهنية افتتاحية تربط المفهوم بالمفاهيم الأساسية للمقرر.",
        )
    )

    # Slide 2: Core Concept & Formal Definition
    slides.append(
        SlideItem(
            slide_number=2,
            title=f"التعريف والأسس النظرية: {clean_topic}",
            bullet_points=[
                "التعريف العلمي الدقيق والخصائص الجوهرية",
                "العناصر المكونة والمحددات الأساسية",
                "الاصطلاحات والمفردات التقنية المرتبطة",
            ],
            presenter_notes="ركز على التعريف الدقيق دون استطراد واطلب من أحد الطلاب صياغة المفهوم بكلماته.",
            visual_suggestion="رسم توضيحي يفكك المفهوم إلى 3 عناصر رئيسية مع أسهم دلالية.",
        )
    )

    # Slide 3: Mechanism & How it Works Under the Hood
    slides.append(
        SlideItem(
            slide_number=3,
            title="الآلية الداخلية ومسار التنفيذ (Under the Hood)",
            bullet_points=[
                "ماذا يحدث داخلياً خطوة بخطوة أثناء التشغيل",
                "تفاعل المكونات والبيانات في الذاكرة / النظام",
                "المراحل الحرجة ونقاط التحول في المسار",
            ],
            presenter_notes="اشرح حركة المؤشر أو تدفق البيانات بحركة اليد أو المؤشر على الرسم.",
            visual_suggestion="مخطط مسار تدفق (Flowchart) أو تخطيط توزيع الذاكرة (Memory Layout).",
        )
    )

    # Slide 4: Real-world Example / Code / Practical Application
    slides.append(
        SlideItem(
            slide_number=4,
            title="التطبيق العملي ونموذج التنفيذ",
            bullet_points=[
                "سيناريو عملي يوضح المفهوم في بيئة حقيقية",
                "تحليل المدخلات والعمليات والمخرجات المتوقعة",
                "⚠️ الفخاخ الشائعة التي يجب تجنبها عملياً",
            ],
            key_formula_or_code="// تطبيق المفهوم عملياً\nvoid execute_concept() {\n    // خطوات التشغيل الفعلي\n}",
            presenter_notes="توقف عند الخطأ الشائع واطرح تساؤلاً: 'ماذا سيحدث لو حذفنا هذا السطر؟'.",
            visual_suggestion="نافذة كود مبرزة مع أسهم تشير للسطور الحرجة وشاشات المخرجات.",
        )
    )

    # Slide 5: Summary, Exam Takeaways & Next Steps
    slides.append(
        SlideItem(
            slide_number=5,
            title="الخلاصة وأهم نقاط الامتحانات",
            bullet_points=[
                "💡 الخلاصة الجوهرية التي لا تُنسى",
                "الأسئلة المتكررة في الامتحانات حول هذا المفهوم",
                "الموضوع التالي المرتبط الذي سننتقل إليه",
            ],
            presenter_notes="اختم بجملة مركزة تلخص كل ما سبق واطلب تقييم الطلاب الذاتي.",
            visual_suggestion="جدول مقارنة ختامي يلخص الفروق والمزايا في نقاط مكثفة.",
        )
    )

    return SlideDeck(
        topic=clean_topic,
        target_audience="طلاب المرحلة الجامعية والدراسات الأكاديمية",
        total_slides=len(slides),
        slides=slides,
        closing_summary=f"عرض تقديمي متكامل يغطي جوانب «{clean_topic}» نظرياً وعملياً وبصرياً.",
    )


def render_slide_deck_to_markdown(deck: SlideDeck) -> str:
    """Format SlideDeck into readable Markdown with clear slide separators."""
    parts = [
        f"# 📊 العرض التقديمي: {deck.topic}",
        f"**الجمهور المستهدف**: {deck.target_audience} | **عدد الشرائح**: {deck.total_slides}\n",
    ]

    for s in deck.slides:
        sub = f" - *{s.subtitle}*" if s.subtitle else ""
        lines = [
            f"---",
            f"## الشريحة {s.slide_number}: {s.title}{sub}",
            "",
            "### المحتوى والنقاط الرئيسية:",
        ]
        for pt in s.bullet_points:
            lines.append(f"- {pt}")

        if s.key_formula_or_code:
            lines.append(f"\n```text\n{s.key_formula_or_code}\n```")

        if s.visual_suggestion:
            lines.append(f"\n🎨 **المقترح البصري للشريحة**: {s.visual_suggestion}")

        if s.presenter_notes:
            lines.append(f"\n🗣️ **ملاحظات المحاضر (Presenter Notes)**:\n> {s.presenter_notes}")

        parts.append("\n".join(lines))

    if deck.closing_summary:
        parts.append(f"\n---\n💡 **خلاصة العرض**: {deck.closing_summary}")

    return "\n\n".join(parts)
