from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    AgentSkill,
    Resource,
    ResourceChunk,
    StudentLearningProfile,
    StudentTopicKnowledge,
    Subject,
    SubjectMembership,
    UserProfile,
)
from app.services.study_agent.agent import AIStudyAgent
from app.services.study_agent.context_selector import DynamicContextSelector
from app.services.study_agent.intent_analyzer import analyze_student_intent
from app.services.study_agent.learning_service import (
    get_or_create_learning_profile,
    get_topic_knowledge_state,
    record_student_learning_evidence,
)
from app.services.study_agent.pedagogy_engine import (
    build_dynamic_pedagogical_instruction,
    sanitize_pedagogical_output,
)
from app.services.study_agent.schemas import (
    AgentIntent,
    ComplexityLevel,
    DisciplineDomain,
    IntentAnalysisResult,
)
from app.services.study_agent.slide_generator import (
    generate_structured_slide_deck,
    render_slide_deck_to_markdown,
)
from app.services.study_agent.tool_registry import TenantAccessDenied, ToolRegistry
from app.services.study_agent.visual_engine import generate_educational_visual


@pytest.fixture
def agent_test_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()

    student = UserProfile(id=uuid.uuid4(), email="student@study.test", role="student", skill_level=4)
    outsider = UserProfile(id=uuid.uuid4(), email="outsider@study.test", role="student", skill_level=1)
    admin = UserProfile(id=uuid.uuid4(), email="admin@study.test", role="admin", skill_level=10)
    session.add_all([student, outsider, admin])
    session.flush()

    subject = Subject(id=uuid.uuid4(), name="Distributed Systems", created_by=admin.id)
    session.add(subject)
    session.flush()

    membership = SubjectMembership(subject_id=subject.id, user_id=student.id)
    session.add(membership)

    res = Resource(
        id=uuid.uuid4(),
        subject_id=subject.id,
        uploaded_by=admin.id,
        file_name="raft_consensus.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        sha256="dummy_sha256_raft",
        storage_provider="neon",
        storage_bucket="ai-documents",
        storage_key="dist/raft.pdf",
        secure_url="https://neon.test/raft.pdf",
        processing_status="ready",
    )
    session.add(res)
    session.flush()

    chunk = ResourceChunk(
        id=uuid.uuid4(),
        resource_id=res.id,
        chunk_index=0,
        page_number=3,
        content="Raft is a consensus algorithm designed as an alternative to Paxos. It relies on leader election and log replication.",
    )
    session.add(chunk)
    session.commit()

    yield session, student, outsider, subject

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ── 1. Intent Analyzer Tests ──────────────────────────────────────────────────

def test_intent_analyzer_classifies_modalities():
    res_greet = analyze_student_intent("مرحبا يا دكتور")
    assert res_greet.primary_intent == AgentIntent.CONVERSATION
    assert res_greet.requires_tools is False

    res_admin = analyze_student_intent("امتى موعد امتحان الميدتيرم وجدول الفاينال؟")
    assert res_admin.primary_intent == AgentIntent.ADMINISTRATIVE
    assert res_admin.is_administrative is True

    res_deep = analyze_student_intent("اشرح لي بالتفصيل الممل خوارزمية Raft من الألف إلى الياء")
    assert res_deep.primary_intent == AgentIntent.DEEP_EXPLANATION
    assert res_deep.complexity == ComplexityLevel.HIGH

    res_slides = analyze_student_intent("عايز بريزنتيشن وسلايدات جاهزة عن الـ Consensus")
    assert res_slides.primary_intent == AgentIntent.SLIDE_PRESENTATION
    assert res_slides.wants_slides is True

    res_visual = analyze_student_intent("ارسم لي خريطة ذهنية ومخطط يوضح الـ Leader Election")
    assert res_visual.wants_visual is True
    assert res_visual.visual_type == "mindmap"

    res_cs = analyze_student_intent("عايز كود C++ لتنفيذ binary search tree وتتبع الذاكرة")
    assert res_cs.discipline == DisciplineDomain.COMPUTER_SCIENCE

    res_brainstorm = analyze_student_intent("عايز عصف ذهني واقتراحات لأفكار مشاريع تخرج")
    assert res_brainstorm.primary_intent == AgentIntent.BRAINSTORMING


# ── 2. Tool Registry Tenant Isolation & Guardrails ───────────────────────────

def test_tool_registry_enforces_tenant_isolation(agent_test_db):
    db, student, outsider, subject = agent_test_db

    # Authorized student can access tools
    tools_student = ToolRegistry(db=db, student_id=student.id, subject_id=subject.id)
    rec = tools_student.execute_tool("get_subject_resources_overview", {})
    assert rec.success is True
    assert rec.result["total_documents"] == 1

    # Unauthorized student must be denied immediately
    with pytest.raises(TenantAccessDenied):
        ToolRegistry(db=db, student_id=outsider.id, subject_id=subject.id)


def test_tool_registry_caching_and_iteration_limit(agent_test_db):
    db, student, _, subject = agent_test_db
    tools = ToolRegistry(db=db, student_id=student.id, subject_id=subject.id)

    # First call: executes
    rec1 = tools.execute_tool("search_subject_resources", {"query": "consensus", "limit": 2})
    assert rec1.success is True
    assert rec1.execution_time_ms > 0

    # Duplicate call with identical args: returns from cache in 0.1ms
    rec2 = tools.execute_tool("search_subject_resources", {"query": "consensus", "limit": 2})
    assert rec2.success is True
    assert rec2.result == rec1.result
    assert rec2.execution_time_ms == 0.1

    # Max calls exceeded
    tools.max_calls = 3
    tools._call_count = 3
    rec_blocked = tools.execute_tool("get_student_learning_context", {})
    assert rec_blocked.success is False
    assert "Exceeded maximum" in rec_blocked.error


# ── 3. Evidence-Based Knowledge Updates ──────────────────────────────────────

def test_passive_ai_explanation_does_not_increment_mastery(agent_test_db):
    db, student, _, subject = agent_test_db

    # Passive explanation delivered by AI
    ev = record_student_learning_evidence(
        student_id=student.id,
        subject_id=subject.id,
        topic_name="Consensus",
        evidence_type="ai_explanation_delivered",
        db=db,
    )
    assert ev.delta_mastery == 0
    k_state = get_topic_knowledge_state(student.id, subject.id, "Consensus", db)
    assert k_state.mastery_score == 0
    assert k_state.interaction_count >= 1


def test_student_demonstrated_comprehension_increments_mastery(agent_test_db):
    db, student, _, subject = agent_test_db

    # Verified evidence: student solved problem correctly
    ev = record_student_learning_evidence(
        student_id=student.id,
        subject_id=subject.id,
        topic_name="Raft Election",
        evidence_type="student_solved_problem",
        understood_concept="Split vote resolution via randomized timers",
        delta_mastery=20,
        db=db,
    )
    assert ev.delta_mastery == 20
    k_state = get_topic_knowledge_state(student.id, subject.id, "Raft Election", db)
    assert k_state.mastery_score == 20
    assert "Split vote resolution via randomized timers" in k_state.understood_concepts


def test_student_misconception_recording(agent_test_db):
    db, student, _, subject = agent_test_db

    ev = record_student_learning_evidence(
        student_id=student.id,
        subject_id=subject.id,
        topic_name="Paxos",
        evidence_type="student_misconception_demonstrated",
        misconception="Confusing round number with ballot value",
        db=db,
    )
    assert ev.delta_mastery == 0
    assert ev.delta_confidence == -10
    k_state = get_topic_knowledge_state(student.id, subject.id, "Paxos", db)
    assert "Confusing round number with ballot value" in k_state.misconceptions


# ── 4. Dynamic Context Selection ─────────────────────────────────────────────

def test_dynamic_context_selector_formats_and_attributes():
    selector = DynamicContextSelector(budget_chars=5000)
    context = selector.assemble_context(
        subject_title="Operating Systems",
        student_profile={
            "skill_level": 5,
            "learning_style": "practical",
            "explanation_depth": "deep_12_step",
            "weak_areas": ["Deadlocks", "Semaphores"],
        },
        passages=[
            {
                "file_name": "ch7_deadlocks.pdf",
                "page_number": 12,
                "content": "A deadlock situation can arise if all four conditions hold simultaneously.",
            }
        ],
        conversation_history=[
            {"role": "user", "content": "ما هي شروط حدوث الـ Deadlock؟"},
            {"role": "assistant", "content": "الشروط الأربعة هي: Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait."},
        ],
    )

    assert "Operating Systems" in context
    assert "[S1] ملف: ch7_deadlocks.pdf" in context
    assert "Deadlocks, Semaphores" in context
    assert "Mutual Exclusion" in context


# ── 5. Pedagogy Engine & Output Sanitization ──────────────────────────────────

def test_pedagogy_instruction_builds_12_steps_for_deep_explanation():
    intent = IntentAnalysisResult(
        primary_intent=AgentIntent.DEEP_EXPLANATION,
        complexity=ComplexityLevel.HIGH,
        discipline=DisciplineDomain.COMPUTER_SCIENCE,
    )
    instruction = build_dynamic_pedagogical_instruction(
        subject_title="Compilers",
        intent=intent,
        skill_level=8,
        explanation_depth="deep_12_step",
    )
    assert "منظومة الـ 12 خطوة التعليمية" in instruction
    assert "التتبع خطوة بخطوة" in instruction
    assert "الأخطاء الشائعة والفخاخ المتكررة (⚠️)" in instruction
    assert "سؤال التقييم الذاتي (Active Recall)" in instruction


def test_sanitize_pedagogical_output_cleans_robotics_and_emojis():
    raw_text = (
        "أهلاً بك يا بطل في منصة ذاكر معي!\n\n"
        "# 🚀 مصفوفة التتبع\n\n"
        "المصفوفة تخزن العناصر متتالية في الذاكرة.\n\n"
        "في الختام أتمنى لك التوفيق!\n"
        "هل تريد المزيد؟"
    )
    cleaned = sanitize_pedagogical_output(raw_text)
    assert "أهلاً بك" not in cleaned
    assert "في الختام" not in cleaned
    assert "هل تريد المزيد" not in cleaned
    assert "# مصفوفة التتبع" in cleaned


# ── 6. Slide Deck Generation & Visual Engine ─────────────────────────────────

def test_slide_deck_generation_and_markdown():
    deck = generate_structured_slide_deck(
        topic="Consensus Algorithms",
        subject_title="Distributed Systems",
        target_slides_count=5,
    )
    assert deck.total_slides == 5
    assert len(deck.slides) == 5

    md = render_slide_deck_to_markdown(deck)
    assert "# 📊 العرض التقديمي: Consensus Algorithms" in md
    assert "الشريحة 1:" in md
    assert "ملاحظات المحاضر (Presenter Notes)" in md


def test_visual_engine_generates_valid_svg():
    artifact = generate_educational_visual(
        topic="Binary Tree Search",
        visual_type="mindmap",
        discipline=DisciplineDomain.COMPUTER_SCIENCE,
    )
    assert artifact.visual_type == "mindmap"
    assert "<svg" in artifact.svg
    assert "</svg>" in artifact.svg


# ── 7. End-to-End AIStudyAgent Execution ─────────────────────────────────────

def test_study_agent_e2e_conversational_fast_path(agent_test_db):
    db, student, _, subject = agent_test_db
    agent = AIStudyAgent(db=db)

    result = agent.process_message(
        student_id=student.id,
        subject_id=subject.id,
        message="مرحبا يا معلمي",
    )
    assert "أهلاً بك! أنا معلمك ومساعدك الأكاديمي" in result.answer
    assert result.execution_trace.intent.primary_intent == AgentIntent.CONVERSATION
    assert len(result.suggested_replies) > 0


def test_study_agent_e2e_academic_query_with_mocked_llm(agent_test_db):
    db, student, _, subject = agent_test_db
    agent = AIStudyAgent(db=db)

    mock_llm_output = "الـ Raft هو بروتوكول توافق إجماعي يعتمد على انتخاب قائد وتسجيل السجلات [S1]."

    with patch("app.services.study_agent.agent.execute_llm_request_via_router", return_value=(mock_llm_output, "gemini-3.5-flash")):
        result = agent.process_message(
            student_id=student.id,
            subject_id=subject.id,
            message="اشرح لي بروتوكول Raft",
        )
        assert "بروتوكول توافق إجماعي" in result.answer
        assert result.execution_trace.model_used == "gemini-3.5-flash"
        assert len(result.execution_trace.tools_executed) >= 2


def test_study_agent_slide_request_generates_slides_deck(agent_test_db):
    db, student, _, subject = agent_test_db
    agent = AIStudyAgent(db=db)

    result = agent.process_message(
        student_id=student.id,
        subject_id=subject.id,
        message="جهز لي بريزنتيشن وسلايدات عن خوارزمية الانتخاب",
    )
    assert result.slides is not None
    assert result.slides.total_slides == 5
    assert "الشريحة 1:" in result.answer
