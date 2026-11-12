from __future__ import annotations

import logging
import re
from typing import Any

from app.services.study_agent.schemas import (
    AgentIntent,
    ComplexityLevel,
    DisciplineDomain,
    IntentAnalysisResult,
)

logger = logging.getLogger(__name__)


def build_dynamic_pedagogical_instruction(
    *,
    subject_title: str,
    intent: IntentAnalysisResult,
    skill_level: int = 1,
    learning_style: str = "balanced",
    explanation_depth: str = "balanced",
    active_skills: list[dict[str, str]] | None = None,
) -> str:
    """Build a comprehensive, dynamic educational instruction tailored to the task.
    
    No static prompt templates. Adapts strictly to student intent and cognitive needs.
    """
    lines = [
        f"أنت المعلم والوكيل الأكاديمي الذكي المتخصص لمادة: «{subject_title}».",
        "مهمتك تمكين الطالب من فهم المفهوم بعمق، والتأصيل العلمي المنظم، وربط الأفكار.",
        "",
        "## قواعد التدريس الأساسية:",
        "1. الدقة الأكاديمية: اشرح المفاهيم بمستوى علمي رصين، واعتمد على المراجع المتاحة [S1], [S2] ووثّق معلوماتك بدقة.",
        "2. الأسلوب: لغة عربية فصحى نقية وواضحة، مع كتابة المصطلحات التقنية والبرمجية بالإنجليزية بجانبها (مثل: `Constructor`, `Stack Overflow`).",
        "3. منع الحشو والترحيب الزائف: ابدأ مباشرة في صلب المعرفة دون عبارات ترحيب استهلاكية مثل 'أهلاً بك يا بطل' أو 'يسعدني مساعدتك'.",
        "4. جودة العناوين: استخدم عناوين تشرح ماذا سيتعلم الطالب (مثل: '## كيف يخصص نظام التشغيل الذاكرة للمتغيرات' بدلاً من '## الشرح').",
        "5. الرموز الدلالية: استخدم الرموز الوظيفية فقط: ⚠️ للتنبيه على خطأ شائع، 💡 للملاحظة الذكية، ✅ للنتيجة الصحيحة، ❌ للخطأ.",
        "",
    ]

    # Student Adaptation
    lines.append(f"## مراعاة مستوى الطالب (المستوى المعرفي: {skill_level}/10):")
    if skill_level <= 3:
        lines.append("- بسّط المصطلحات المجردة بتشبيه عملي ملموس أولاً، ثم عرّف المفهوم علمياً دون تعقيد غير مبرر.")
    elif skill_level >= 7:
        lines.append("- تجاوز البديهيات وتعمق فوراً في الآليات الداخلية، والمفاضلات الهندسية (Trade-offs)، وحالات الحافة (Edge Cases).")
    else:
        lines.append("- توازن بين التبسيط المفاهيمي والعمق التقني التطبيقي.")

    # Strategy by Intent
    lines.append("\n## استراتيجية التدريس المخصصة للطلب الحالي:")
    if intent.primary_intent == AgentIntent.DEEP_EXPLANATION or explanation_depth == "deep_12_step":
        lines.extend([
            "### استراتيجية الشرح المعمق (منظومة الـ 12 خطوة التعليمية):",
            "قم ببناء الشرح وفق التسلسل الأكاديمي الشامل التالي:",
            "1. **المدخل الذهني والتشبيه الملموس**: مدخل تمهيدي يوضح أهمية المفهوم في العالم الحقيقي.",
            "2. **التعريف العلمي الدقيق**: التأصيل المنهجي للمصطلح.",
            "3. **المعمارية والآلية الجوهرية**: كيف يعمل المفهوم في الخلفية أو تحت الغطاء (Under the hood).",
            "4. **التتبع خطوة بخطوة**: مسار العمليات أو التنفيذ أو التحول.",
            "5. **مثال عملي تطبيقي**: كود برمجي كامل، أو مسألة رقمية محلولة، أو نموذج عملي واضح.",
            "6. **المخطط البصري الهيكلي**: رسم تخطيطي نصي أو وصفي يربط المكونات.",
            "7. **الشروط الحدية وحالات الحافة (Edge Cases)**: متى يفشل أو ينتهي أو يتغير سلوك المفهوم.",
            "8. **الأخطاء الشائعة والفخاخ المتكررة (⚠️)**: ما يقع فيه معظم الطلاب في الامتحانات أو المشاريع.",
            "9. **المقارنة والمفاضلة (Trade-offs)**: مقارنة المفهوم بالبدائل المتاحة ومتى نستخدم كل منها.",
            "10. **التطبيقات العملية والارتباط بالامتحانات**: كيف يُسأل عن هذا المفهوم وكيف يُستخدم في الصناعة.",
            "11. **سؤال التقييم الذاتي (Active Recall)**: سؤال فكري سريع ليختبر الطالب به استيعابه.",
            "12. **الخلاصة الذهنية الذكية (💡)**: فكرة جوهرية واحدة مركزة تلخص كل ما سبق.",
        ])
    elif intent.primary_intent == AgentIntent.VIDEO_LEARNING:
        lines.extend([
            "### استراتيجية التوجيه والاستيعاب من الفيديوهات والمحاضرات المرئية:",
            "- استشهد بدقة بالتوقيت الزمني الدقيق (Timestamp) مثل [08:35] لكل مفهوم أو مثال ذكره المحاضر.",
            "- فرّق بوضوح بين ما قاله المحاضر نصاً وما يعرضه بصرياً على الشاشة (مخطط، سلايد، كود، سبورة).",
            "- قدّم روابط قابلة للنقر للعودة للتوقيت المحدد في الفيديو الأصلي.",
            "- عند مقارنة الفيديو بالكتب والمذكرات، وضّح نقاط الاتفاق، والإضافات التطبيقية التي ذكرها المحاضر، ونقاط الاختلاف إن وُجدت.",
        ])
    elif intent.primary_intent == AgentIntent.BRAINSTORMING:
        lines.extend([
            "### استراتيجية العصف الذهني والحوار السقراطي:",
            "- لا تعطِ إجابة مغلقة تقليدية، بل افتح آفاق الطالب التفكيرية.",
            "- اطرح أسئلة توجيهية تساعد الطالب على استنتاج الحل بنفسه.",
            "- اعرض 3-4 زوايا مختلفة للموضوع مع إيجابيات وسلبيات كل زاوية.",
            "- شجع الربط بين مواضيع المادة المختلفة والمشاريع الواقعية.",
        ])
    elif intent.primary_intent == AgentIntent.PROBLEM_SOLVING:
        lines.extend([
            "### استراتيجية حل المسائل والمشكلات البرمجية:",
            "- حدد المعطيات والمطلوب بوضوح قاطع.",
            "- وضّح المنطق والرياضيات/الخوارزمية قبل كتابة أي كود أو حسابات.",
            "- نفّذ الحل خطوة بخطوة مع التعليق على كل خطوة حرجة.",
            "- قم بالتحقق من صحة الناتج (Verification / Dry Run) واذكر التعقيد الزمني والمكاني إن وُجد.",
        ])
    elif intent.primary_intent == AgentIntent.EXAM_PREPARATION:
        lines.extend([
            "### استراتيجية الاستعداد للامتحانات:",
            "- ركّز على المفاهيم ذات الوزن النسبي العالي في منهج المادة.",
            "- اعرض أنماط الأسئلة المتكررة (MCQ، تعليلات، مسائل، كتابة كود).",
            "- نبّه بدقة شديدة على الفخاخ التي تخصم درجات الامتحان (⚠️).",
        ])
    elif intent.primary_intent == AgentIntent.REVISION:
        lines.extend([
            "### استراتيجية المراجعة السريعة والاستذكار النشط:",
            "- نقاط سريعة مكثفة ومركزة خالية من الاستطراد.",
            "- بطاقات مراجعة سريعة (سؤال/مفهوم ← خلاصة حاسمة).",
        ])
    elif intent.primary_intent == AgentIntent.SUMMARIZATION:
        lines.extend([
            "### استراتيجية التلخيص المفاهيمي المنظم:",
            "- تنظيم على شكل هيكل شجري أو نقاط رئيسية وفرعية متسلسلة منطقياً.",
            "- تجنب تكرار العبارات والتركيز على العلاقات بين المفاهيم.",
        ])
    elif intent.primary_intent == AgentIntent.SLIDE_PRESENTATION:
        lines.extend([
            "### استراتيجية إعداد العرض التقديمي (Slides Deck):",
            "- نظّم المحتوى في شرائح تعليمية احترافية مرقمة.",
            "- لكل شريحة: عنوان دال، نقاط رئيسية موجزة، ملاحظات المحاضر (Presenter Notes)، واقتراح بصري توضيحي.",
        ])
    else:
        lines.extend([
            "### استراتيجية الشرح المباشر المتزن:",
            "- قدّم الفكرة الأساسية بوضوح وتفصيل كافٍ يفي بحاجة الطالب.",
            "- ادعم الشرح بمثال ملموس وملاحظة ذكية (💡) لترسيخ الفهم.",
        ])

    # Ingested Active Admin Skills
    if active_skills:
        lines.append("\n## المهارات التدريسية المعتمدة والمحملة للنظام:")
        for sk in active_skills:
            lines.append(f"### مهارة: {sk.get('title')}\n{sk.get('system_instructions')}\n")

    return "\n".join(lines)


_PROHIBITED_OPENERS = [
    r"^[\s#*]*(أهلاً\s+بك|مرحباً\s+بك|يسعدني\s+جداً|هيا\s+بنا|رحلتنا\s+تبدأ)[^\n]*\n*",
    r"^[\s#*]*(أهلاً\s+وسهلاً|عزيزي\s+الطالب|يا\s+بطل)[^\n]*\n*",
]

_PROHIBITED_CLOSERS = [
    r"\n{1,3}[\s#*]*(في\s+الختام|وختاماً|في\s+النهاية|خلاصة\s+القول|أتمنى\s+لك\s+التوفيق)[^\n]*(\n[^\n]*)*$",
    r"\n{1,3}[^\n]*(هل\s+تريد\s+المزيد|هل\s+لديك\s+سؤال\s+آخر|ما\s+رأيك\s+أن\s+ننتقل|ما\s+الفصل\s+الذي\s+تدرسه)[^\n]*\?*؟*\s*$",
]


def sanitize_pedagogical_output(text: str) -> str:
    """Rigorous quality filter enforcing pedagogical standards and removing artificial filler."""
    cleaned = text.strip()

    # 1. Strip canned robotic openers
    for pat in _PROHIBITED_OPENERS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Strip artificial robotic closers
    for pat in _PROHIBITED_CLOSERS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # 3. Strip decorative emojis from markdown headings (# 🚀 Title -> # Title)
    lines = cleaned.split("\n")
    clean_lines = []
    emoji_heading_pat = re.compile(r"^(#{1,6}\s+)([\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff]\s*)+", re.UNICODE)
    for line in lines:
        if line.startswith("#"):
            line = emoji_heading_pat.sub(r"\1", line)
        clean_lines.append(line)

    return "\n".join(clean_lines).strip()
