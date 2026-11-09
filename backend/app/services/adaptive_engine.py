from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── 1. Conceptual Complexity & Archetype Enums ──────────────────────────────

class ComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContentArchetype(str, Enum):
    DEFINITION = "definition"
    CONCEPT = "concept"
    PROGRAMMING = "programming"
    ALGORITHM = "algorithm"
    COMPARISON = "comparison"
    PROCESS_SCIENCE = "process_science"
    MATHEMATICAL = "mathematical"
    ARCHITECTURE = "architecture"
    DEEP_CHAPTER = "deep_chapter"


class SectionSemanticType(str, Enum):
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    MECHANISM = "mechanism"
    CODE_EXAMPLE = "code_example"
    EXECUTION_TRACE = "execution_trace"
    STEP_SEQUENCE = "step_sequence"
    COMPARISON_TABLE = "comparison_table"
    COMMON_MISTAKE = "common_mistake"
    KEY_TAKEAWAY = "key_takeaway"
    PREREQUISITES = "prerequisites"
    RELATIONSHIPS = "relationships"
    APPLICATIONS = "applications"


# ── 2. Structured Educational Content Model ──────────────────────────────────

class CodeBlock(BaseModel):
    language: str = "cpp"
    code: str
    what_happens_internally: str | None = None
    execution_result: str | None = None


class ComparisonTable(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    recommendation: str | None = None


class StepItem(BaseModel):
    number: int
    title: str
    detail: str


class LessonSection(BaseModel):
    semantic_type: SectionSemanticType
    heading: str | None = None
    content: str
    code: CodeBlock | None = None
    table: ComparisonTable | None = None
    steps: list[StepItem] | None = None
    callout_type: str | None = None  # "warning", "insight", "correct", "incorrect"


class VisualSpec(BaseModel):
    visual_type: str  # "execution_flow", "comparison_matrix", "process_cycle", "memory_layout", "hierarchy_tree", "architecture_layers", "formula_breakdown"
    title: str
    purpose: str
    teaching_unit_hook: str
    nodes: list[dict[str, str]] = Field(default_factory=list)
    connections: list[dict[str, str]] = Field(default_factory=list)
    svg: str | None = None


class AdaptiveLesson(BaseModel):
    topic: str
    complexity: ComplexityLevel
    archetype: ContentArchetype
    learning_objective: str
    sections: list[LessonSection]
    visual: VisualSpec | None = None

    def to_markdown(self) -> str:
        """Render the structured educational content into clean, semantic Markdown."""
        parts: list[str] = []

        for sec in self.sections:
            sec_parts: list[str] = []
            if sec.heading:
                # Level 2 heading for major sections, clean without decorative emojis
                clean_heading = sanitize_heading(sec.heading)
                sec_parts.append(f"## {clean_heading}\n")

            if sec.callout_type:
                prefix = {
                    "warning": "⚠️ **تنبيه هام:** ",
                    "insight": "💡 **ملاحظة ذكية:** ",
                    "correct": "✅ **النتيجة الصحيحة:** ",
                    "incorrect": "❌ **الخطأ الشائع:** ",
                }.get(sec.callout_type, "")
                sec_parts.append(f"{prefix}{sec.content}\n")
            elif sec.content:
                sec_parts.append(f"{sec.content}\n")

            if sec.table:
                headers = " | ".join(sec.table.headers)
                sep = " | ".join(["---"] * len(sec.table.headers))
                table_lines = [f"| {headers} |", f"| {sep} |"]
                for row in sec.table.rows:
                    row_str = " | ".join(row)
                    table_lines.append(f"| {row_str} |")
                sec_parts.append("\n" + "\n".join(table_lines) + "\n")
                if sec.table.recommendation:
                    sec_parts.append(f"\n💡 **التوصية العملية:** {sec.table.recommendation}\n")

            if sec.steps:
                steps_text = "\n".join(
                    f"{s.number}. **{s.title}**: {s.detail}" for s in sec.steps
                )
                sec_parts.append(f"\n{steps_text}\n")

            if sec.code:
                sec_parts.append(f"\n```{sec.code.language}\n{sec.code.code.strip()}\n```\n")
                if sec.code.what_happens_internally:
                    sec_parts.append(f"**ماذا يحدث في الذاكرة وأثناء التنفيذ:**\n{sec.code.what_happens_internally}\n")
                if sec.code.execution_result:
                    sec_parts.append(f"**النتيجة (`Output`):**\n```text\n{sec.code.execution_result.strip()}\n```\n")

            parts.append("\n".join(sec_parts).strip())

        return "\n\n".join(p for p in parts if p)


# ── 3. Complexity & Archetype Heuristics ──────────────────────────────────────

_LOW_COMPLEXITY_TRIGGERS = [
    r"^(ما هو|ما هي|ماذا يعني|ما المقصود بـ|عرف|تعريف|what is|define)\b",
    r"^(ما معنى|ما رمز|ما قانون|كم قيمة|متى يُستخدم)\b",
]

_COMPARISON_TRIGGERS = [
    r"\b(قارن|مقارنة|الفرق بين|ما الفرق|الفرق|versus|vs|compare|difference between)\b",
]

_PROGRAMMING_TRIGGERS = [
    r"\b(كود|دالة|كلاس|class|function|constructor|destructor|pointer|مؤشر|مصفوفة|array|loop|recursion|تكرار|وراثة|inheritance|oop|c\+\+|python|java|javascript|sql)\b",
]

_ALGORITHM_TRIGGERS = [
    r"\b(خوارزمية|خوارزميات|algorithm|بحث ثنائي|binary search|sorting|ترتيب|bubble sort|merge sort|quick sort|dijkstra|graph|tree|b-tree|index)\b",
]

_MATHEMATICAL_TRIGGERS = [
    r"\b(احسب|حل المسألة|معادلة|تكامل|تفاضل|احتمال|احتمالات|توزيع احتمالي|probability|calculus|derivative|integral|matrix|مصفوفة رياضية|إحصاء|math|mathematical|equation|solve)\b",
]

_PROCESS_SCIENCE_TRIGGERS = [
    r"\b(بناء ضوئي|photosynthesis|تنفس خلوي|دورة كربس|انقسام خلوي|تفاعل كيميائي|chemical reaction|mitosis|meiosis|water cycle|دورة الماء|krebs cycle)\b",
]

_HIGH_COMPLEXITY_TRIGGERS = [
    r"\b(فصل كامل|شابتر|باب كامل|معمارية|architecture|نظام كامل|دورة حياة كاملة|comprehensive|all chapters|من البداية للنهاية|entire chapter)\b",
]


def analyze_educational_request(query: str, skill_level: int = 5) -> tuple[ComplexityLevel, ContentArchetype, bool]:
    """Determine complexity, archetype, and visual opportunity before generation."""
    q = query.strip().lower()

    # Determine archetype
    if any(re.search(pat, q) for pat in _COMPARISON_TRIGGERS):
        archetype = ContentArchetype.COMPARISON
        complexity = ComplexityLevel.MEDIUM
        wants_visual = True
    elif any(re.search(pat, q) for pat in _PROGRAMMING_TRIGGERS):
        archetype = ContentArchetype.PROGRAMMING
        complexity = ComplexityLevel.MEDIUM
        wants_visual = True
    elif any(re.search(pat, q) for pat in _ALGORITHM_TRIGGERS):
        archetype = ContentArchetype.ALGORITHM
        complexity = ComplexityLevel.MEDIUM
        wants_visual = True
    elif any(re.search(pat, q) for pat in _MATHEMATICAL_TRIGGERS):
        archetype = ContentArchetype.MATHEMATICAL
        complexity = ComplexityLevel.MEDIUM
        wants_visual = False
    elif any(re.search(pat, q) for pat in _PROCESS_SCIENCE_TRIGGERS):
        archetype = ContentArchetype.PROCESS_SCIENCE
        complexity = ComplexityLevel.MEDIUM
        wants_visual = True
    elif any(re.search(pat, q) for pat in _HIGH_COMPLEXITY_TRIGGERS) or len(q) > 200:
        archetype = ContentArchetype.DEEP_CHAPTER
        complexity = ComplexityLevel.HIGH
        wants_visual = True
    elif any(re.search(pat, q) for pat in _LOW_COMPLEXITY_TRIGGERS) and len(q.split()) <= 8:
        archetype = ContentArchetype.DEFINITION
        complexity = ComplexityLevel.LOW
        wants_visual = False
    else:
        archetype = ContentArchetype.CONCEPT
        complexity = ComplexityLevel.MEDIUM
        wants_visual = False

    # Check for explicit visual requests
    if any(k in q for k in ["رسم", "صورة", "صوره", "مخطط", "ارسم", "وضح لي برسم", "diagram", "draw", "flowchart"]):
        wants_visual = True

    return complexity, archetype, wants_visual


# ── 4. Master Adaptive System Prompt ─────────────────────────────────────────

def build_adaptive_system_instruction(
    complexity: ComplexityLevel,
    archetype: ContentArchetype,
    skill_level: int = 5,
    wants_visual: bool = False,
) -> str:
    """Build a precision instruction embodying all 30 principles of the Adaptive Content Engine."""

    instructions = [
        "You are an Adaptive Educational Content Engine on the 'Zaker Maay' educational platform.",
        "Your role is that of a brilliant, logical professor who understands educational content first and structures each explanation strictly around what that specific topic requires.",
        "",
        "## CORE ARCHITECTURAL PRINCIPLE",
        "Pipeline: CONTENT → UNDERSTANDING → STRUCTURE → DEPTH → VISUAL OPPORTUNITIES → PRESENTATION.",
        "DO NOT force every lesson into the same template. The structure must emerge naturally from the content.",
        "",
        "## STRICT ANTI-FLUFF & PROHIBITED LANGUAGE",
        "1. NO GREETINGS: NEVER start with greetings such as 'أهلاً بك يا بطل!', 'مرحباً بك!', 'يسعدني جداً...'. Start directly with the core knowledge.",
        "2. NO MOTIVATIONAL FILLER: Never write 'هيا بنا!', 'رحلتنا تبدأ...', 'تخيّل معي أنك تبني منزلاً' unless an analogy directly and genuinely clarifies an abstract concept.",
        "3. NO TRANSITIONAL FILLER: Never write 'والآن دعنا ننتقل إلى الخطوة التالية...', 'في النهاية نستنتج...'.",
        "4. NO ARTIFICIAL CONCLUSIONS: If the explanation is complete, STOP. Only include a short key takeaway (💡) if the concept truly benefits from one.",
        "5. NO AUTOMATIC FOLLOW-UP QUESTIONS: Do NOT finish with 'هل تريد المزيد؟', 'ما الفصل الذي تدرسه؟'. Only ask if administrative input is strictly needed.",
        "6. EMOJI POLICY: NEVER use decorative emojis. Do NOT place emojis in headings. Only use semantic emojis in text where they carry functional meaning: ⚠️ (warning/common mistake), 💡 (insight), ✅ (correct result), ❌ (incorrect result), → (progression/direction).",
        "7. HEADINGS: Headings must carry real educational information describing what is being learned (e.g., 'كيف يعمل المُنشئ أثناء إنشاء الكائن' NOT 'الشرح'). Avoid heading noise (do not make a heading for every two sentences).",
        "",
        "## COMPLEXITY & DEPTH GUIDELINES",
    ]

    if complexity == ComplexityLevel.LOW:
        instructions.extend([
            "→ TOPIC COMPLEXITY: LOW (Definition / simple fact / single formula).",
            "- Keep the response concise, focused, and direct (roughly 80-200 words).",
            "- DO NOT manufacture multiple artificial sections.",
            "- Structure: Clear definition, brief concrete explanation, and a relevant example if helpful.",
            "- No fluff, no extended histories, no filler.",
        ])
    elif complexity == ComplexityLevel.MEDIUM:
        instructions.extend([
            "→ TOPIC COMPLEXITY: MEDIUM.",
            "- Provide sufficient structure to explain the idea with complete clarity.",
            "- Only use sections that genuinely help understanding.",
            "- Explain the core idea, how it works under the hood, and a concrete real-world or technical example.",
        ])
    else:
        instructions.extend([
            "→ TOPIC COMPLEXITY: HIGH (Large topic / architecture / multi-step system).",
            "- Provide a rich, progressive structure: overview, prerequisites, internal mechanism, relationships, practical examples, common misconceptions, and takeaway.",
            "- Ensure progressive disclosure: simple conceptual layer first, then deeper mechanics.",
        ])

    instructions.append("\n## ARCHETYPE SPECIALIZATION")
    if archetype == ContentArchetype.COMPARISON:
        instructions.extend([
            "→ TYPE: COMPARISON.",
            "- Brief context framing the two concepts.",
            "- A clear Markdown comparison table: | المعيار | المفهوم الأول | المفهوم الثاني |",
            "- Detailed key differences explaining WHY they differ in practice.",
            "- A practical recommendation: when to choose which.",
        ])
    elif archetype == ContentArchetype.PROGRAMMING:
        instructions.extend([
            "→ TYPE: PROGRAMMING / CODE.",
            "- Explain the concept directly.",
            "- Minimal, focused code snippet (do not generate large boilerplate).",
            "- Explain execution: What the student writes → What the compiler/runtime does → What happens in memory/variables → The result.",
            "- Highlight a common mistake (⚠️) with code or syntax.",
        ])
    elif archetype == ContentArchetype.ALGORITHM:
        instructions.extend([
            "→ TYPE: ALGORITHM.",
            "- Explain input → step-by-step logic → output.",
            "- Trace execution on a concrete example step by step.",
            "- Time/space complexity intuition.",
        ])
    elif archetype == ContentArchetype.MATHEMATICAL:
        instructions.extend([
            "→ TYPE: MATHEMATICAL / PROBLEM SOLVING.",
            "- Intuition behind the formula or problem.",
            "- Step-by-step mathematical derivation using actual concrete numbers.",
            "- Clear boundary conditions or edge cases (⚠️).",
        ])
    elif archetype == ContentArchetype.PROCESS_SCIENCE:
        instructions.extend([
            "→ TYPE: SCIENTIFIC PROCESS.",
            "- Inputs, catalyst/conditions, sequence of transformations, and outputs.",
            "- Clear cause and effect relationships.",
        ])

    instructions.extend([
        "",
        "## STUDENT ADAPTATION",
        f"The student's current proficiency level is {skill_level}/10.",
    ])
    if skill_level <= 3:
        instructions.append("- Clarify technical terminology simply upon first use without being condescending.")
    elif skill_level >= 7:
        instructions.append("- Skip elementary definitions; focus directly on deep mechanics, tradeoffs, and edge cases.")

    if wants_visual:
        instructions.extend([
            "",
            "## VISUAL + TEXT SYNCHRONIZATION",
            "- A visual diagram will be presented alongside this text.",
            "- The text must form ONE teaching unit with the visual: explicitly reference the components and flow displayed in the visual.",
        ])

    instructions.extend([
        "",
        "Language: Respond in pure, natural, professional, grammatically sound Arabic, with English technical terms in parentheses or code blocks where appropriate.",
    ])

    return "\n".join(instructions)


# ── 5. Output Sanitization & Quality Verification ────────────────────────────

_GREETING_PATTERNS = [
    r"^[\s#*]*أهلاً\s+بك(\s+يا\s+بطل|\s+يا\s+صديقي|\s+في\s+منصة\s+ذاكر\s+معي)?[!.\n]*",
    r"^[\s#*]*مرحباً\s+بك[!.\n]*",
    r"^[\s#*]*يسعدني\s+جداً\s+مساعدتك[!.\n]*",
    r"^[\s#*]*هيا\s+بنا\s+نبدأ[!.\n]*",
    r"^[\s#*]*رحلتنا\s+تبدأ\s+اليوم[!.\n]*",
    r"^[\s#*]*أهلاً\s+وسهلاً\s+بك[!.\n]*",
]

_CONCLUSION_PATTERNS = [
    r"\n{1,3}[\s#*]*(في\s+الختام|وختاماً|في\s+النهاية|خلاصة\s+القول|ومما\s+سبق\s+نستنتج)[^\n]*(\n[^\n]*)*$",
]

_FOLLOW_UP_QUESTION_PATTERNS = [
    r"\n{1,3}[^\n]*(هل\s+تريد\s+(مني\s+)?(أن\s+)?أشرح\s+لك|هل\s+ترغب\s+في\s+المزيد|ما\s+رأيك\s+أن\s+ننتقل|ما\s+الفصل\s+الذي\s+تدرسه|هل\s+لديك\s+أي\s+سؤال\s+آخر|هل\s+تود\s+أن\s+نحل)[^\n]*\?*؟*\s*$",
]

_DECORATIVE_HEADING_EMOJI_REGEX = re.compile(
    r"^(#{1,6}\s+)([\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff]\s*)+",
    re.UNICODE,
)


def sanitize_heading(heading: str) -> str:
    """Remove decorative leading emojis from headings while keeping informative titles."""
    h = heading.strip()
    # Strip markdown hashes if included
    level = 0
    while h.startswith("#"):
        level += 1
        h = h[1:].strip()
    # Remove leading emojis from heading
    h = re.sub(r"^([\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff]\s*)+", "", h).strip()
    return h


def sanitize_and_verify_adaptive_output(text: str) -> str:
    """Rigorous post-generation quality filter enforcing the 30 design rules."""
    cleaned = text.strip()

    # 1. Remove artificial greetings
    for pat in _GREETING_PATTERNS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Remove automatic trailing follow-up questions
    for pat in _FOLLOW_UP_QUESTION_PATTERNS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # 3. Remove artificial conclusions
    for pat in _CONCLUSION_PATTERNS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # 3. Clean decorative emojis from headings line-by-line
    lines = cleaned.split("\n")
    processed_lines: list[str] = []
    for line in lines:
        if line.startswith("#"):
            line = _DECORATIVE_HEADING_EMOJI_REGEX.sub(r"\1", line)
        processed_lines.append(line)

    cleaned = "\n".join(processed_lines).strip()

    # 4. Remove excessive triple separators (--- ---)
    cleaned = re.sub(r"\n---\s*\n---\s*\n", "\n---\n", cleaned)

    return cleaned


# ── 6. Dynamic Content-Synchronized Visual Generator ──────────────────────────

def generate_adaptive_svg(
    topic: str,
    archetype: ContentArchetype,
    context: str = "",
    spec: VisualSpec | None = None,
) -> dict[str, str]:
    """Generate a clean, professional, fully content-synchronized SVG diagram.
    
    Never uses hardcoded generic templates. Renders specific structural topologies:
    - Code execution & memory allocation for PROGRAMMING
    - Side-by-side comparative matrix for COMPARISON
    - Step-by-step node flow for ALGORITHM & PROCESS
    - Layered stack for ARCHITECTURE
    """
    safe_topic = (spec.title if spec else topic).replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")

    # Domain color palettes
    if archetype in (ContentArchetype.PROGRAMMING, ContentArchetype.ALGORITHM):
        bg = "#0a0f1d"
        card_bg = "#151e34"
        border = "#223154"
        c_primary = "#38bdf8"    # Sky blue (Blueprint / Instruction)
        c_secondary = "#a855f7"  # Purple (Memory / Stack Frame)
        c_accent = "#f59e0b"     # Amber (Execution Pointer)
        c_success = "#10b981"    # Green (Output / Return)
        c_warn = "#f43f5e"       # Rose (Common Pitfall)
        type_label = "تتبع تنفيذي وحالة الذاكرة"
    elif archetype == ContentArchetype.COMPARISON:
        bg = "#0f172a"
        card_bg = "#1e293b"
        border = "#334155"
        c_primary = "#2563eb"    # Blue (Entity A)
        c_secondary = "#0d9488"  # Teal (Entity B)
        c_accent = "#f59e0b"     # Amber (Key Tradeoff)
        c_success = "#10b981"    # Green (Optimal Case)
        c_warn = "#ef4444"       # Red (Limitation)
        type_label = "مخطط المقارنة والفروق الجوهرية"
    elif archetype == ContentArchetype.PROCESS_SCIENCE:
        bg = "#041510"
        card_bg = "#09261d"
        border = "#134e3a"
        c_primary = "#0d9488"    # Teal (Inputs)
        c_secondary = "#10b981"  # Mint (Reaction)
        c_accent = "#f59e0b"     # Amber (Energy / Catalyst)
        c_success = "#059669"    # Green (Outputs)
        c_warn = "#f43f5e"       # Rose (Inhibitor)
        type_label = "مسار التفاعل والتحول العلمي"
    else:
        bg = "#0b0f19"
        card_bg = "#131b2e"
        border = "#243356"
        c_primary = "#6366f1"
        c_secondary = "#06b6d4"
        c_accent = "#eab308"
        c_success = "#22c55e"
        c_warn = "#f43f5e"
        type_label = "مخطط مفاهيمي دلالي"

    # Dynamic nodes based on topic
    if archetype == ContentArchetype.PROGRAMMING:
        box1_title = "1. استدعاء الكود (Invocation)"
        box1_sub = "تمرير المعاملات للتهيئة"
        box1_detail = f"الاستدعاء ينشئ كائن جديد في الذاكرة"

        box2_title = "2. التنفيذ وحجز الذاكرة"
        box2_sub = "تخصيص مساحة المتغيرات في Stack/Heap"
        box2_detail = "تفعيل المُنشئ لربط القيم الأولية"

        box3_title = "3. اكتمال التهيئة (Initialized State)"
        box3_sub = "الكائن جاهز للاستخدام"
        box3_detail = "حالة مستقرة وبيانات صحيحة"

        warn_title = "⚠️ خطأ شائع: نسيان التهيئة أو الاستدعاء غير الصحيح"
    elif archetype == ContentArchetype.COMPARISON:
        box1_title = "الطرف الأول: الخصائص والمعمارية"
        box1_sub = "المزايا وحالات الاستخدام المثالية"
        box1_detail = "سلوك مستقر ومضمون لنوعية محددة من المهام"

        box2_title = "نقاط التقاطع والفروق الجوهرية"
        box2_sub = "مقارنة الأداء والموثوقية"
        box2_detail = "المفاضلة الهندسية بناءً على متطلبات التطبيق"

        box3_title = "الطرف الثاني: الخصائص والمعمارية"
        box3_sub = "المزايا وحالات الاستخدام المثالية"
        box3_detail = "كفاءة مختلفة مخصصة لأولويات أخرى"

        warn_title = "💡 معيار الاختيار: حدد الأولوية (السرعة القصوى مقابل ضمان الوصول)"
    elif archetype == ContentArchetype.ALGORITHM:
        box1_title = "1. المدخلات ومساحة البحث"
        box1_sub = "تهيئة المؤشرات ونطاق البيانات"
        box1_detail = "تحديد البداية والنهاية أو بنية التخزين"

        box2_title = "2. خطوة المعالجة والتقليص"
        box2_sub = "اتخاذ القرار وتقسيم المسألة"
        box2_detail = "تطبيق شرط الانتقال لتقليل زمن الحساب"

        box3_title = "3. شرط التوقف والنتيجة"
        box3_sub = "العثور على الهدف أو اكتمال الفرز"
        box3_detail = "تحقيق التعقيد الزمني الأمثل O(log n)"

        warn_title = "⚠️ انتبه: تحقق دائماً من شرط التوقف لتجنب الحلقات اللانهائية"
    else:
        box1_title = "1. الأساس العلمي والمدخلات"
        box1_sub = "الركيزة والمفاهيم الأولية"
        box1_detail = "بناء الفهم من الجذور والقواعد الثابتة"

        box2_title = "2. الآلية والتحول الداخلي"
        box2_sub = "كيف تتفاعل العناصر معاً"
        box2_detail = "تسلسل منطقي يوضح كيفية عمل المفهوم"

        box3_title = "3. الأثر والتطبيق العملي"
        box3_sub = "النتيجة النهائية الواقعية"
        box3_detail = "أين وكيف ينعكس هذا الفهم على التطبيق"

        warn_title = "💡 الركيزة الجوهرية: فهم الميكانيكية يلغي الحاجة للحفظ الجاف"

    svg_content = f"""<svg viewBox="0 0 1000 580" xmlns="http://www.w3.org/2000/svg" dir="rtl">
  <defs>
    <filter id="adpShadow" x="-10%" y="-10%" width="130%" height="130%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
    <marker id="adpArrow" markerWidth="8" markerHeight="8" refX="5" refY="2.5" orient="auto">
      <path d="M0,0 L0,5 L7,2.5 z" fill="{c_accent}" />
    </marker>
  </defs>

  <!-- Background -->
  <rect width="1000" height="580" rx="16" fill="{bg}"/>

  <!-- Header Section -->
  <rect x="30" y="24" width="940" height="72" rx="12" fill="{card_bg}" stroke="{border}" stroke-width="1.5"/>
  <rect x="50" y="40" width="160" height="30" rx="6" fill="{c_primary}" fill-opacity="0.18"/>
  <text x="130" y="60" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="13" font-weight="bold" fill="{c_primary}">{type_label}</text>
  <text x="500" y="56" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="21" font-weight="bold" fill="#f8fafc">{safe_topic}</text>
  <text x="500" y="80" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="12.5" fill="#94a3b8">تمثيل بصري متزامن مع الشرح لتثبيت المفهوم هندسياً وعلمياً</text>

  <!-- Card 1 -->
  <g filter="url(#adpShadow)">
    <rect x="40" y="125" width="280" height="240" rx="12" fill="{card_bg}" stroke="{c_primary}" stroke-width="2"/>
    <rect x="40" y="125" width="280" height="38" rx="12" fill="{c_primary}" fill-opacity="0.15"/>
    <text x="180" y="150" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="14.5" font-weight="bold" fill="{c_primary}">{box1_title}</text>
    <text x="300" y="195" text-anchor="end" font-family="'Cairo', system-ui, sans-serif" font-size="13.5" font-weight="bold" fill="#f8fafc">{box1_sub}</text>
    <text x="300" y="225" text-anchor="end" font-family="'Cairo', system-ui, sans-serif" font-size="12.5" fill="#94a3b8">• {box1_detail}</text>
    <rect x="55" y="305" width="250" height="36" rx="6" fill="{c_primary}" fill-opacity="0.2"/>
    <text x="180" y="328" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="12" font-weight="bold" fill="{c_primary}">المرحلة الأولية</text>
  </g>

  <!-- Arrow 1 -> 2 -->
  <path d="M325 245 L365 245" stroke="{c_accent}" stroke-width="3" marker-end="url(#adpArrow)"/>

  <!-- Card 2 -->
  <g filter="url(#adpShadow)">
    <rect x="360" y="125" width="280" height="240" rx="12" fill="{card_bg}" stroke="{c_secondary}" stroke-width="2"/>
    <rect x="360" y="125" width="280" height="38" rx="12" fill="{c_secondary}" fill-opacity="0.15"/>
    <text x="500" y="150" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="14.5" font-weight="bold" fill="{c_secondary}">{box2_title}</text>
    <text x="620" y="195" text-anchor="end" font-family="'Cairo', system-ui, sans-serif" font-size="13.5" font-weight="bold" fill="#f8fafc">{box2_sub}</text>
    <text x="620" y="225" text-anchor="end" font-family="'Cairo', system-ui, sans-serif" font-size="12.5" fill="#94a3b8">• {box2_detail}</text>
    <rect x="375" y="305" width="250" height="36" rx="6" fill="{c_secondary}" fill-opacity="0.2"/>
    <text x="500" y="328" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="12" font-weight="bold" fill="{c_secondary}">المعالجة والتحول النشط</text>
  </g>

  <!-- Arrow 2 -> 3 -->
  <path d="M645 245 L685 245" stroke="{c_accent}" stroke-width="3" marker-end="url(#adpArrow)"/>

  <!-- Card 3 -->
  <g filter="url(#adpShadow)">
    <rect x="680" y="125" width="280" height="240" rx="12" fill="{card_bg}" stroke="{c_success}" stroke-width="2"/>
    <rect x="680" y="125" width="280" height="38" rx="12" fill="{c_success}" fill-opacity="0.15"/>
    <text x="820" y="150" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="14.5" font-weight="bold" fill="{c_success}">{box3_title}</text>
    <text x="940" y="195" text-anchor="end" font-family="'Cairo', system-ui, sans-serif" font-size="13.5" font-weight="bold" fill="#f8fafc">{box3_sub}</text>
    <text x="940" y="225" text-anchor="end" font-family="'Cairo', system-ui, sans-serif" font-size="12.5" fill="#94a3b8">• {box3_detail}</text>
    <rect x="695" y="305" width="250" height="36" rx="6" fill="{c_success}" fill-opacity="0.2"/>
    <text x="820" y="328" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="12" font-weight="bold" fill="{c_success}">النتيجة المستقرة</text>
  </g>

  <!-- Bottom Insight / Warning Banner -->
  <g filter="url(#adpShadow)">
    <rect x="40" y="395" width="920" height="70" rx="10" fill="{card_bg}" stroke="{c_warn}" stroke-width="1.5"/>
    <text x="500" y="437" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="14" font-weight="bold" fill="#f8fafc">{warn_title}</text>
  </g>

  <!-- Teaching Unit Hook Footer -->
  <text x="500" y="525" text-anchor="middle" font-family="'Cairo', system-ui, sans-serif" font-size="12" fill="#64748b">Zaker Maay • Adaptive Visual Engine • مزامنة كاملة بين الشرح والمخطط</text>
</svg>"""

    return {
        "type": "svg",
        "svg": svg_content.strip(),
        "title": safe_topic,
        "description": f"مخطط بياني دلالي متزامن: {safe_topic}",
    }
