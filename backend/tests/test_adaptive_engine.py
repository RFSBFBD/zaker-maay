import pytest
from app.services.adaptive_engine import (
    ComplexityLevel,
    ContentArchetype,
    SectionSemanticType,
    CodeBlock,
    ComparisonTable,
    StepItem,
    LessonSection,
    VisualSpec,
    AdaptiveLesson,
    analyze_educational_request,
    build_adaptive_system_instruction,
    sanitize_heading,
    sanitize_and_verify_adaptive_output,
    generate_adaptive_svg,
)


def test_analyze_educational_request_low_complexity() -> None:
    complexity, archetype, wants_visual = analyze_educational_request("ما هو المتغير؟")
    assert complexity == ComplexityLevel.LOW
    assert archetype == ContentArchetype.DEFINITION
    assert wants_visual is False


def test_analyze_educational_request_programming() -> None:
    complexity, archetype, wants_visual = analyze_educational_request("What is a constructor in C++?")
    assert archetype == ContentArchetype.PROGRAMMING
    assert complexity == ComplexityLevel.MEDIUM
    assert wants_visual is True


def test_analyze_educational_request_comparison() -> None:
    complexity, archetype, wants_visual = analyze_educational_request("قارن بين TCP و UDP")
    assert archetype == ContentArchetype.COMPARISON
    assert complexity == ComplexityLevel.MEDIUM
    assert wants_visual is True


def test_analyze_educational_request_algorithm() -> None:
    complexity, archetype, wants_visual = analyze_educational_request("اشرح خوارزمية البحث الثنائي binary search")
    assert archetype == ContentArchetype.ALGORITHM
    assert complexity == ComplexityLevel.MEDIUM
    assert wants_visual is True


def test_analyze_educational_request_mathematics() -> None:
    complexity, archetype, wants_visual = analyze_educational_request("حل المسألة واحسب التكامل للدالة")
    assert archetype == ContentArchetype.MATHEMATICAL
    assert complexity == ComplexityLevel.MEDIUM


def test_analyze_educational_request_deep_chapter() -> None:
    complexity, archetype, wants_visual = analyze_educational_request("اشرح هذا الفصل كامل من البداية للنهاية مع المعمارية")
    assert complexity == ComplexityLevel.HIGH
    assert archetype == ContentArchetype.DEEP_CHAPTER
    assert wants_visual is True


def test_build_adaptive_system_instruction_contains_anti_fluff_rules() -> None:
    instruction = build_adaptive_system_instruction(
        complexity=ComplexityLevel.LOW,
        archetype=ContentArchetype.DEFINITION,
        skill_level=3,
        wants_visual=False,
    )
    assert "NO GREETINGS" in instruction
    assert "NO MOTIVATIONAL FILLER" in instruction
    assert "NO ARTIFICIAL CONCLUSIONS" in instruction
    assert "NO AUTOMATIC FOLLOW-UP QUESTIONS" in instruction
    assert "DO NOT manufacture multiple artificial sections" in instruction


def test_build_adaptive_system_instruction_comparison_specialization() -> None:
    instruction = build_adaptive_system_instruction(
        complexity=ComplexityLevel.MEDIUM,
        archetype=ContentArchetype.COMPARISON,
        skill_level=6,
        wants_visual=True,
    )
    assert "Markdown comparison table" in instruction
    assert "VISUAL + TEXT SYNCHRONIZATION" in instruction


def test_sanitize_heading_removes_decorative_emojis() -> None:
    assert sanitize_heading("## 🚀 1. مفهوم المُنشئ") == "1. مفهوم المُنشئ"
    assert sanitize_heading("### ✨ آلية العمل") == "آلية العمل"
    assert sanitize_heading("المفهوم الأساسي") == "المفهوم الأساسي"


def test_sanitize_and_verify_adaptive_output_strips_greetings_and_conclusions() -> None:
    dirty = (
        "أهلاً بك يا بطل! يسعدني جداً مساعدتك.\n\n"
        "## 🚀 مفهوم الوراثة في البرمجة\n"
        "الوراثة تعني تمكين كلاس فرعي من اكتساب صفات ودوال كلاس أساسي.\n\n"
        "في النهاية نكون قد فهمنا الوراثة.\n\n"
        "هل تريد مني أن أشرح لك مثالاً آخر؟"
    )
    cleaned = sanitize_and_verify_adaptive_output(dirty)

    assert "أهلاً بك يا بطل" not in cleaned
    assert "يسعدني جداً" not in cleaned
    assert "🚀" not in cleaned
    assert "## مفهوم الوراثة في البرمجة" in cleaned
    assert "في النهاية" not in cleaned
    assert "هل تريد مني أن أشرح" not in cleaned


def test_adaptive_lesson_to_markdown() -> None:
    lesson = AdaptiveLesson(
        topic="المُنشئ في C++",
        complexity=ComplexityLevel.MEDIUM,
        archetype=ContentArchetype.PROGRAMMING,
        learning_objective="فهم آلية تهيئة الكائن عند إنشائه",
        sections=[
            LessonSection(
                semantic_type=SectionSemanticType.DEFINITION,
                heading="كيف يعمل المُنشئ أثناء إنشاء الكائن",
                content="المُنشئ دالة خاصة بنفس اسم الكلاس تُنفذ تلقائياً عند حجز مساحة الكائن في الذاكرة.",
            ),
            LessonSection(
                semantic_type=SectionSemanticType.CODE_EXAMPLE,
                heading="مثال برمجي وتتبع التنفيذ",
                content="تعريف كلاس Box مع مُنشئ يستقبل الأبعاد:",
                code=CodeBlock(
                    language="cpp",
                    code="class Box {\npublic:\n    int w, h;\n    Box(int a, int b) : w(a), h(b) {}\n};",
                    what_happens_internally="يتم تمرير القيم إلى قائمة التهيئة وتعيينها في حقول الكائن مباشرة داخل الذاكرة.",
                    execution_result="تم إنشاء الكائن بنجاح وتخصيص المتغيرات.",
                ),
            ),
            LessonSection(
                semantic_type=SectionSemanticType.COMMON_MISTAKE,
                content="تجنب تعريف كائن بدون معاملات إذا لم يكن هناك Default Constructor معرف.",
                callout_type="warning",
            ),
        ],
    )

    md = lesson.to_markdown()
    assert "## كيف يعمل المُنشئ أثناء إنشاء الكائن" in md
    assert "```cpp" in md
    assert "ماذا يحدث في الذاكرة وأثناء التنفيذ:" in md
    assert "⚠️ **تنبيه هام:**" in md


def test_generate_adaptive_svg_programming() -> None:
    result = generate_adaptive_svg(
        topic="Constructor in C++",
        archetype=ContentArchetype.PROGRAMMING,
    )
    assert result["type"] == "svg"
    assert "<svg" in result["svg"]
    assert "تتبع تنفيذي وحالة الذاكرة" in result["svg"]
    assert "Constructor in C++" in result["svg"]
