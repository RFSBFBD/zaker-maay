import pytest
from app.services.adaptive_engine import (
    ComplexityLevel,
    ContentArchetype,
    analyze_educational_request,
    build_adaptive_system_instruction,
    sanitize_and_verify_adaptive_output,
    generate_adaptive_svg,
    AdaptiveLesson,
    LessonSection,
    SectionSemanticType,
    CodeBlock,
    ComparisonTable,
    StepItem,
)


RADICAL_10_PROMPTS = [
    ("What is a constructor in C++?", ContentArchetype.PROGRAMMING, ComplexityLevel.MEDIUM, True),
    ("Explain recursion.", ContentArchetype.PROGRAMMING, ComplexityLevel.MEDIUM, True),
    ("Compare TCP and UDP.", ContentArchetype.COMPARISON, ComplexityLevel.MEDIUM, True),
    ("Explain probability distributions.", ContentArchetype.MATHEMATICAL, ComplexityLevel.MEDIUM, False),
    ("How does a database index work?", ContentArchetype.ALGORITHM, ComplexityLevel.MEDIUM, True),
    ("Explain binary search.", ContentArchetype.ALGORITHM, ComplexityLevel.MEDIUM, True),
    ("What is inheritance in OOP?", ContentArchetype.PROGRAMMING, ComplexityLevel.MEDIUM, True),
    ("Explain photosynthesis.", ContentArchetype.PROCESS_SCIENCE, ComplexityLevel.MEDIUM, True),
    ("Solve this mathematical problem.", ContentArchetype.MATHEMATICAL, ComplexityLevel.MEDIUM, False),
    ("Explain this entire chapter.", ContentArchetype.DEEP_CHAPTER, ComplexityLevel.HIGH, True),
]


def test_radical_10_prompts_produce_diverse_classifications() -> None:
    """Verify that all 10 prompts are mapped to distinct, content-appropriate archetypes and depths."""
    seen_archetypes = set()
    visual_counts = {True: 0, False: 0}

    for prompt, expected_archetype, expected_complexity, expected_visual in RADICAL_10_PROMPTS:
        complexity, archetype, wants_visual = analyze_educational_request(prompt)

        assert archetype == expected_archetype, f"Expected {expected_archetype} for '{prompt}', got {archetype}"
        assert complexity == expected_complexity, f"Expected {expected_complexity} for '{prompt}', got {complexity}"
        assert wants_visual == expected_visual, f"Expected visual={expected_visual} for '{prompt}', got {wants_visual}"

        seen_archetypes.add(archetype)
        visual_counts[wants_visual] += 1

    # Ensure diversity across the archetypes: we should cover at least 5 distinct archetypes
    assert len(seen_archetypes) >= 5
    # Ensure visual generation is selective, not a mindless yes for every single prompt
    assert visual_counts[True] > 0
    assert visual_counts[False] > 0


def test_radical_10_prompts_system_instructions_are_content_driven() -> None:
    """Verify that the generated instructions differ significantly based on the topic archetype."""
    instructions = {}
    for prompt, archetype, complexity, wants_visual in RADICAL_10_PROMPTS:
        instruction = build_adaptive_system_instruction(
            complexity=complexity,
            archetype=archetype,
            skill_level=5,
            wants_visual=wants_visual,
        )
        instructions[prompt] = instruction

        # Universal Anti-Fluff checks
        assert "NO GREETINGS" in instruction
        assert "NO MOTIVATIONAL FILLER" in instruction
        assert "NO ARTIFICIAL CONCLUSIONS" in instruction
        assert "NO AUTOMATIC FOLLOW-UP QUESTIONS" in instruction

    # Archetype-specific checks:
    # 1. Comparison must mandate a comparison table
    assert "Markdown comparison table" in instructions["Compare TCP and UDP."]
    assert "Markdown comparison table" not in instructions["Explain recursion."]

    # 2. Programming must mandate execution trace and memory effect
    assert "What happens in memory/variables" in instructions["What is a constructor in C++?"]

    # 3. Math must mandate concrete numerical derivation
    assert "actual concrete numbers" in instructions["Solve this mathematical problem."]

    # 4. Deep chapter must mandate progressive disclosure and broad structure
    assert "HIGH" in instructions["Explain this entire chapter."]


def test_radical_10_outputs_have_different_structures_and_no_boilerplate() -> None:
    """Verify simulated lessons across the 10 prompts have distinct structures and section counts."""
    # 1. Low/Medium Programming: Constructor
    lesson_constructor = AdaptiveLesson(
        topic="C++ Constructor",
        complexity=ComplexityLevel.MEDIUM,
        archetype=ContentArchetype.PROGRAMMING,
        learning_objective="Understand object initialization",
        sections=[
            LessonSection(
                semantic_type=SectionSemanticType.DEFINITION,
                heading="كيف يعمل المُنشئ أثناء إنشاء الكائن",
                content="المُنشئ دالة خاصة بنفس اسم الكلاس تُنفذ تلقائياً عند حجز مساحة الكائن في الذاكرة.",
            ),
            LessonSection(
                semantic_type=SectionSemanticType.CODE_EXAMPLE,
                heading="مثال برمجي وتتبع التنفيذ",
                content="تعريف كلاس مع مُنشئ:",
                code=CodeBlock(language="cpp", code="Box b(10, 20);", what_happens_internally="حجز الذاكرة وتعيين 10 و 20"),
            ),
            LessonSection(
                semantic_type=SectionSemanticType.COMMON_MISTAKE,
                content="تجنب تعريف كائن بدون معاملات عند غياب default constructor.",
                callout_type="warning",
            ),
        ],
    )

    # 2. Comparison: TCP vs UDP
    lesson_tcp_udp = AdaptiveLesson(
        topic="TCP vs UDP",
        complexity=ComplexityLevel.MEDIUM,
        archetype=ContentArchetype.COMPARISON,
        learning_objective="Compare connection-oriented vs connectionless protocols",
        sections=[
            LessonSection(
                semantic_type=SectionSemanticType.EXPLANATION,
                heading="السياق والهدف من البروتوكولين",
                content="بروتوكولان في طبقة النقل يقدمان آليات مختلفة لنقل الحزم.",
            ),
            LessonSection(
                semantic_type=SectionSemanticType.COMPARISON_TABLE,
                heading="جدول المقارنة المباشرة",
                content="أبرز الفروق الجوهرية:",
                table=ComparisonTable(
                    headers=["المعيار", "TCP", "UDP"],
                    rows=[
                        ["الموثوقية", "عالية (مع مصافحة وإعادة إرسال)", "منخفضة (بدون ضمان)"],
                        ["السرعة", "أبطأ بسبب التتبع", "أسرع بأقل هيدر"],
                        ["الاستخدام", "تصفح الويب ونقل الملفات", "البث الحي والألعاب"],
                    ],
                    recommendation="اختر TCP لسلامة البيانات، وUDP للسرعة الفائقة.",
                ),
            ),
        ],
    )

    # 3. High Complexity: Entire Chapter
    lesson_chapter = AdaptiveLesson(
        topic="معمارية المعالجات وأنظمة التشغيل",
        complexity=ComplexityLevel.HIGH,
        archetype=ContentArchetype.DEEP_CHAPTER,
        learning_objective="استيعاب العلاقة بين العتاد والبرمجيات",
        sections=[
            LessonSection(semantic_type=SectionSemanticType.PREREQUISITES, heading="المتطلبات الأساسية", content="فهم الذاكرة والمسجلات."),
            LessonSection(semantic_type=SectionSemanticType.MECHANISM, heading="آلية عمل دورة الجلب والتنفيذ", content="جلب التعليمة ثم فك تشفيرها ثم تنفيذها."),
            LessonSection(semantic_type=SectionSemanticType.STEP_SEQUENCE, heading="خطوات مقاطعة المعالج", content="تسلسل استجابة المقاطعة:", steps=[
                StepItem(number=1, title="حفظ الحالة", detail="حفظ مسجلات البرنامج الحالي."),
                StepItem(number=2, title="تنفيذ الروتين", detail="الانتقال لجدول المقاطعات."),
            ]),
            LessonSection(semantic_type=SectionSemanticType.KEY_TAKEAWAY, content="الفصل يربط بين سرعة الساعة وكفاءة خط الأنابيب (Pipelining).", callout_type="insight"),
        ],
    )

    md_constructor = lesson_constructor.to_markdown()
    md_tcp = lesson_tcp_udp.to_markdown()
    md_chapter = lesson_chapter.to_markdown()

    # Structural diversity assertions:
    # 1. Section counts are different:
    assert len(lesson_constructor.sections) == 3
    assert len(lesson_tcp_udp.sections) == 2
    assert len(lesson_chapter.sections) == 4

    # 2. Content formats are different:
    assert "```cpp" in md_constructor
    assert "| المعيار | TCP | UDP |" in md_tcp
    assert "1. **حفظ الحالة**:" in md_chapter

    # 3. Zero greetings and zero fake endings in all:
    for md in (md_constructor, md_tcp, md_chapter):
        assert "أهلاً بك يا بطل" not in md
        assert "في النهاية" not in md
        assert "هل تريد" not in md


def test_radical_svg_generation_differs_by_archetype() -> None:
    """Verify that generated SVGs have different domain palettes, topologies, and labels."""
    svg_prog = generate_adaptive_svg("Constructor in C++", ContentArchetype.PROGRAMMING)
    svg_comp = generate_adaptive_svg("TCP vs UDP", ContentArchetype.COMPARISON)
    svg_algo = generate_adaptive_svg("Binary Search", ContentArchetype.ALGORITHM)

    assert svg_prog["type"] == "svg"
    assert svg_comp["type"] == "svg"
    assert svg_algo["type"] == "svg"

    # Different topology headers and subtitles:
    assert "تتبع تنفيذي وحالة الذاكرة" in svg_prog["svg"]
    assert "مخطط المقارنة والفروق الجوهرية" in svg_comp["svg"]
    assert "1. المدخلات ومساحة البحث" in svg_algo["svg"]
    assert "الطرف الأول: الخصائص والمعمارية" in svg_comp["svg"]
