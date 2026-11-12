from __future__ import annotations

import re

from app.services.study_agent.schemas import (
    AgentIntent,
    ComplexityLevel,
    DisciplineDomain,
    IntentAnalysisResult,
)

# ── Pattern matchers ─────────────────────────────────────────────────────────

_GREETING_PATTERNS = [
    r"^(مرحبا|أهلا|اهلا|سلام|السلام عليكم|صباح الخير|مساء الخير|شكرا|شكرًا|تسلم|يعطيك العافية|hi|hello|hey|thanks|thank you)\b",
]

_ADMIN_PATTERNS = [
    r"\b(موعد|ميعاد|جدول|فاينال|ميدتيرم|درجات|أعمال سنة|أعمال السنه|ملغي|دكتور|تسليم|شيت|امتى الامتحان|متى الامتحان)\b",
]

_SLIDE_PATTERNS = [
    r"\b(سلايد|سلايدات|عرض تقديمي|بريزنتيشن|بوربوينت|شرائح|slides?|presentation|powerpoint)\b",
]

_VIDEO_PATTERNS = [
    r"\b(فيديو|محاضرة مسجلة|يوتيوب|المحاضر قال|في الفيديو|شرح الفيديو|الدقيقة|توقيت|فيديو الشرح|youtube|video|timestamp)\b",
    r"https?://(www\.)?(youtube\.com|youtu\.be)/",
]

_VISUAL_PATTERNS = [
    r"\b(ارسم|صورة|صوره|رسمة|رسمه|مخطط|دياجرام|خريطة ذهنية|خريطه ذهنيه|خريطة مفاهيم|انفوجرافيك|diagram|draw|mindmap|mind\s*map|visual|flowchart|sketch)\b",
]

_BRAINSTORM_PATTERNS = [
    r"\b(عصف ذهني|أفكار|افكار|نقاش|فكر معايا|فكر معي|اقتراحات|اقترح|brainstorm|brainstorming|ideas?|explore concepts?)\b",
]

_PROBLEM_SOLVING_PATTERNS = [
    r"\b(حل المسألة|حل المسالة|احسب|معادلة|حل الكود|كود|تتبع|trace|debug|error|exception|solve|calculate|equation|مشكلة في الكود)\b",
]

_EXAM_PREP_PATTERNS = [
    r"\b(امتحان|كويز|اختبار|اختبرني|امتحني|أسئلة متوقعة|اسئلة متوقعة|مراجعة ليلة الامتحان|exam|quiz|test me)\b",
]

_REVISION_PATTERNS = [
    r"\b(راجع لي|راجعلي|مراجعة سريعة|استذكار|تذكير|فلاش كارد|بطاقات|summary review|quick recap|revision|flashcards?)\b",
]

_SUMMARIZATION_PATTERNS = [
    r"\b(لخص|تلخيص|ملخص|أوجز|اوجز|summary|summarize|brief)\b",
]

_DEEP_EXPLANATION_PATTERNS = [
    r"\b(اشرح بالتفصيل|شرح عميق|من الألف إلى الياء|من الصفر|بالتفصيل الممل|فصل كامل|شابتر كامل|deep explanation|explain in depth|comprehensive)\b",
]

_CS_KEYWORDS = [
    "كود", "دالة", "كلاس", "مؤشر", "مصفوفة", "خوارزمية", "شجرة", "ذاكرة", "برمجة",
    "class", "function", "pointer", "array", "algorithm", "tree", "graph", "stack", "heap",
    "python", "c++", "java", "sql", "oop", "database", "recursion"
]

_MATH_KEYWORDS = [
    "معادلة", "تكامل", "تفاضل", "احتمال", "مصفوفة رياضية", "إحصاء", "متغير عشوائي",
    "integral", "derivative", "matrix", "probability", "statistics", "calculus", "vector"
]

_SCIENCE_KEYWORDS = [
    "خلية", "تفاعل", "كيمياء", "فيزياء", "طاقة", "حركة", "دورة", "إنزيم",
    "cell", "reaction", "chemistry", "physics", "energy", "cycle", "enzyme", "mitosis"
]


def analyze_student_intent(message: str) -> IntentAnalysisResult:
    """Analyze the student's message with semantic precision."""
    cleaned = message.strip()
    lower = cleaned.lower()

    if not cleaned:
        return IntentAnalysisResult(
            primary_intent=AgentIntent.CONVERSATION,
            requires_tools=False,
            requires_rag=False,
            expected_outcome="Conversational reply",
        )

    # 1. Direct short greeting or polite reply
    is_pure_greeting = (
        len(cleaned.split()) <= 4
        and any(re.search(pat, lower) for pat in _GREETING_PATTERNS)
        and not any(re.search(pat, lower) for pat in _VISUAL_PATTERNS + _SLIDE_PATTERNS + _PROBLEM_SOLVING_PATTERNS)
    )
    if is_pure_greeting:
        return IntentAnalysisResult(
            primary_intent=AgentIntent.CONVERSATION,
            requires_tools=False,
            requires_rag=False,
            expected_outcome="Friendly educational greeting and assistance offer",
        )

    # 2. Administrative inquiry check
    is_admin = any(re.search(pat, lower) for pat in _ADMIN_PATTERNS)

    # 3. Slide presentation intent
    wants_slides = any(re.search(pat, lower) for pat in _SLIDE_PATTERNS)

    # 4. Visual intent
    wants_visual = any(re.search(pat, lower) for pat in _VISUAL_PATTERNS)
    visual_type = None
    if wants_visual:
        if "خريطة ذهنية" in lower or "خريطه ذهنيه" in lower or "mindmap" in lower:
            visual_type = "mindmap"
        elif "مقارنة" in lower or "فرق" in lower or "comparison" in lower:
            visual_type = "comparison"
        elif "تدفق" in lower or "مسار" in lower or "flowchart" in lower:
            visual_type = "flowchart"
        elif "معمارية" in lower or "architecture" in lower or "طبقات" in lower:
            visual_type = "architecture"
        else:
            visual_type = "concept_diagram"

    # 5. Primary intent identification
    primary = AgentIntent.EXPLANATION
    secondary: list[AgentIntent] = []

    if is_admin:
        primary = AgentIntent.ADMINISTRATIVE
    elif any(re.search(pat, lower) for pat in _VIDEO_PATTERNS):
        primary = AgentIntent.VIDEO_LEARNING
    elif wants_slides:
        primary = AgentIntent.SLIDE_PRESENTATION
    elif any(re.search(pat, lower) for pat in _DEEP_EXPLANATION_PATTERNS):
        primary = AgentIntent.DEEP_EXPLANATION
    elif any(re.search(pat, lower) for pat in _BRAINSTORM_PATTERNS):
        primary = AgentIntent.BRAINSTORMING
    elif any(re.search(pat, lower) for pat in _PROBLEM_SOLVING_PATTERNS):
        primary = AgentIntent.PROBLEM_SOLVING
    elif any(re.search(pat, lower) for pat in _EXAM_PREP_PATTERNS):
        primary = AgentIntent.EXAM_PREPARATION
    elif any(re.search(pat, lower) for pat in _REVISION_PATTERNS):
        primary = AgentIntent.REVISION
    elif any(re.search(pat, lower) for pat in _SUMMARIZATION_PATTERNS):
        primary = AgentIntent.SUMMARIZATION
    elif wants_visual and len(cleaned.split()) <= 7:
        primary = AgentIntent.VISUAL_LEARNING

    if wants_visual and primary != AgentIntent.VISUAL_LEARNING:
        secondary.append(AgentIntent.VISUAL_LEARNING)
    if wants_slides and primary != AgentIntent.SLIDE_PRESENTATION:
        secondary.append(AgentIntent.SLIDE_PRESENTATION)

    # 6. Discipline classification
    discipline = DisciplineDomain.GENERAL
    if any(k in lower for k in _CS_KEYWORDS):
        discipline = DisciplineDomain.COMPUTER_SCIENCE
    elif any(k in lower for k in _MATH_KEYWORDS):
        discipline = DisciplineDomain.MATHEMATICS
    elif any(k in lower for k in _SCIENCE_KEYWORDS):
        discipline = DisciplineDomain.NATURAL_SCIENCES

    # 7. Complexity classification
    complexity = ComplexityLevel.MEDIUM
    word_count = len(cleaned.split())
    if word_count > 30 or primary in (AgentIntent.DEEP_EXPLANATION, AgentIntent.SLIDE_PRESENTATION):
        complexity = ComplexityLevel.HIGH
    elif word_count <= 8 and primary in (AgentIntent.CONVERSATION, AgentIntent.RETRIEVAL):
        complexity = ComplexityLevel.LOW

    # 8. Expected outcome formulation
    outcome_map = {
        AgentIntent.CONVERSATION: "Engaging and supportive educational dialogue",
        AgentIntent.ADMINISTRATIVE: "Referral to academic administration with guidance",
        AgentIntent.SLIDE_PRESENTATION: "Structured educational slide deck with key points and notes",
        AgentIntent.VISUAL_LEARNING: "Educational diagram, mindmap, or visual schematic",
        AgentIntent.DEEP_EXPLANATION: "Comprehensive 12-step pedagogical breakdown",
        AgentIntent.BRAINSTORMING: "Socratic exploration, conceptual connections, and idea generation",
        AgentIntent.PROBLEM_SOLVING: "Rigorous step-by-step resolution with verification",
        AgentIntent.EXAM_PREPARATION: "Exam-oriented practice questions and targeted tips",
        AgentIntent.REVISION: "Active recall summary and memory consolidation",
        AgentIntent.SUMMARIZATION: "Concise, structured conceptual summary",
        AgentIntent.EXPLANATION: "Clear, grounded educational explanation",
        AgentIntent.RETRIEVAL: "Accurate citation of course materials",
    }
    expected_outcome = outcome_map.get(primary, "Grounded educational answer")

    requires_rag = primary not in (AgentIntent.CONVERSATION, AgentIntent.ADMINISTRATIVE)
    requires_tools = primary != AgentIntent.CONVERSATION

    return IntentAnalysisResult(
        primary_intent=primary,
        secondary_intents=secondary,
        discipline=discipline,
        complexity=complexity,
        requires_tools=requires_tools,
        requires_rag=requires_rag,
        wants_visual=wants_visual,
        visual_type=visual_type,
        wants_slides=wants_slides,
        expected_outcome=expected_outcome,
        is_administrative=is_admin,
    )
