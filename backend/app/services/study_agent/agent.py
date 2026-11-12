from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentSkill,
    ChatMessage as DBChatMessage,
    ChatThread,
    OrchestratorDecision,
    Resource,
    Subject,
    UserProfile,
    YouTubeLink,
)
from app.services import gemini as gemini_service
from app.services.study_agent.context_selector import DynamicContextSelector
from app.services.study_agent.intent_analyzer import analyze_student_intent
from app.services.study_agent.pedagogy_engine import (
    build_dynamic_pedagogical_instruction,
    sanitize_pedagogical_output,
)
from app.services.study_agent.router_adapter import (
    execute_llm_request_via_router,
    map_intent_to_router_task_type,
)
from app.services.study_agent.schemas import (
    AgentExecutionTrace,
    AgentIntent,
    AgentRunResult,
    ExecutionStepPlan,
    IntentAnalysisResult,
    ToolCallRecord,
)
from app.services.study_agent.slide_generator import (
    generate_structured_slide_deck,
    render_slide_deck_to_markdown,
)
from app.services.study_agent.tool_registry import TenantAccessDenied, ToolRegistry
from app.services.study_agent.visual_engine import generate_educational_visual

logger = logging.getLogger(__name__)


class AIStudyAgent:
    """Adaptive Educational Orchestrator Agent.
    
    Transforms the interaction architecture into an adaptive AI Study Agent
    instructing the existing AI Router layer.
    """

    def __init__(self, db: Session):
        self.db = db
        self.context_selector = DynamicContextSelector()

    def process_message(
        self,
        *,
        student_id: UUID,
        subject_id: UUID,
        message: str,
        thread_id: UUID | None = None,
    ) -> AgentRunResult:
        """Execute the full agent reasoning, tool execution, and synthesis cycle."""
        start_time = time.perf_counter()
        req_id = str(uuid.uuid4())

        # 1. Tenant & Subject Verification
        subject = self.db.get(Subject, subject_id)
        if not subject:
            raise TenantAccessDenied("المادة الدراسية غير موجودة.")

        user = self.db.get(UserProfile, student_id)
        skill_level = user.skill_level if user else 1

        # 2. Intent Analysis
        intent_res = analyze_student_intent(message)
        logger.info(
            "Agent analyzed intent for student %s on subject %s: %s (complexity: %s)",
            student_id,
            subject_id,
            intent_res.primary_intent.value,
            intent_res.complexity.value,
        )

        trace = AgentExecutionTrace(
            request_id=req_id,
            student_id=str(student_id),
            subject_id=str(subject_id),
            user_message=message,
            intent=intent_res,
        )

        # 3. Fast Path: Pure Conversational Greeting (No wasteful tool or DB queries)
        if intent_res.primary_intent == AgentIntent.CONVERSATION:
            greeting_ans = (
                f"أهلاً بك! أنا معلمك ومساعدك الأكاديمي لمادة «{subject.name}». 📚\n\n"
                "أنا جاهز للإجابة على أي مفهوم في المنهج، أو شرح المسائل المعقدة بالتفصيل، "
                "أو تصميم خرائط ذهنية ومخططات بصرية، أو تجهيز سلايدات مراجعة واختبارات تفاعلية. "
                "بماذا تود أن نبدأ اليوم؟"
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            trace.duration_ms = round(elapsed_ms, 2)
            self._log_decision(subject_id, "conversation", trace, greeting_ans, True)
            return AgentRunResult(
                answer=greeting_ans,
                execution_trace=trace,
                suggested_replies=[
                    f"اشرح لي أهم موضوع في {subject.name}",
                    "اعمل لي خريطة ذهنية للمقرر",
                    "جهز لي عرض تقديمي سريع",
                ],
            )

        # 4. Fast Path: Administrative Question (Out of scope for tutor AI)
        if intent_res.primary_intent == AgentIntent.ADMINISTRATIVE:
            admin_ans = (
                "هذا استفسار إداري أو تنظيمي يخص مواعيد الامتحانات أو الجداول أو أعضاء هيئة التدريس. "
                "يرجى مراجعة إدارة الكلية أو أستاذ المادة مباشرة للحصول على المعلومات الرسمية المعتمدة."
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            trace.duration_ms = round(elapsed_ms, 2)
            self._log_decision(subject_id, "administrative", trace, admin_ans, True)
            return AgentRunResult(
                answer=admin_ans,
                execution_trace=trace,
                out_of_scope=True,
                suggested_replies=[
                    f"اشرح لي المفهوم العلمي في {subject.name}",
                    "ساعدني في حل مسألة دراسية",
                ],
            )

        # 5. Check if Subject Has Any Uploaded Materials
        has_res = self.db.scalar(
            select(func.count(Resource.id)).where(Resource.subject_id == subject_id)
        ) or 0
        has_yt = self.db.scalar(
            select(func.count(YouTubeLink.id)).where(YouTubeLink.subject_id == subject_id)
        ) or 0

        if (has_res + has_yt) == 0:
            no_res_ans = (
                "لم تقم برفع أي ملفات أو مصادر لهذه المادة بعد! 📚\n\n"
                "ارفع كتبك، ملازمك، أو محاضراتك الصوتية لكي أتمكن من قراءتها وشرحها ومساعدتك فيها بدقة خطوة بخطوة."
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            trace.duration_ms = round(elapsed_ms, 2)
            self._log_decision(subject_id, "no_resources", trace, no_res_ans, True)
            return AgentRunResult(
                answer=no_res_ans,
                execution_trace=trace,
                no_resources=True,
            )

        # 6. Initialize Tool Registry with Tenant Isolation
        tools = ToolRegistry(db=self.db, student_id=student_id, subject_id=subject_id)

        # 7. Execute Plan Step 1: Fetch Student Learning Profile
        prof_record = tools.execute_tool("get_student_learning_context", {})
        trace.tools_executed.append(prof_record)
        student_prof = prof_record.result if prof_record.success else {}

        # 8. Execute Plan Step 2: Fetch Conversation Context (if thread provided)
        conv_history = []
        if thread_id:
            hist_record = tools.execute_tool(
                "get_conversation_history",
                {"thread_id": str(thread_id), "limit": 4},
            )
            trace.tools_executed.append(hist_record)
            if hist_record.success:
                conv_history = hist_record.result.get("messages", [])

        # 9. Execute Plan Step 3: Retrieval / Subject Overview
        overview_record = tools.execute_tool("get_subject_resources_overview", {})
        trace.tools_executed.append(overview_record)
        subject_overview = overview_record.result if overview_record.success else {}

        meta_triggers = ["ملف", "مكتبه", "مكتبة", "محتوى", "محتوي", "اشرح لي", "اشرحلي", "لخص", "لخصلي", "ابدأ", "امتحانات", "منهج", "الموجود"]
        is_meta = any(k in message.lower() for k in meta_triggers)

        passages = []
        rag_record = tools.execute_tool("search_subject_resources", {"query": message, "limit": 6})
        trace.tools_executed.append(rag_record)
        if rag_record.success:
            passages = rag_record.result.get("passages", [])

        # 9.1 Academic Hierarchy & Prerequisite Discovery
        ch_record = tools.execute_tool("get_subject_academic_chapters", {})
        trace.tools_executed.append(ch_record)
        academic_chapters = ch_record.result.get("chapters", []) if ch_record.success else []
        missing_chapters = ch_record.result.get("missing_chapters", []) if ch_record.success else []

        prereq_record = tools.execute_tool("get_concept_with_prerequisites", {"query": message})
        trace.tools_executed.append(prereq_record)
        prerequisites = prereq_record.result.get("prerequisites", []) if prereq_record.success else []

        conflict_record = tools.execute_tool("get_cross_document_connections", {})
        trace.tools_executed.append(conflict_record)
        conflicts = conflict_record.result.get("conflicts", []) if conflict_record.success else []

        # 9.2 Video Understanding & Timestamped Retrieval
        yt_match = re.search(r"https?://(www\.)?(youtube\.com|youtu\.be)/[^\s]+", message)
        if yt_match:
            yt_url = yt_match.group(0)
            vid_record = tools.execute_tool("analyze_video_url", {"url": yt_url})
            trace.tools_executed.append(vid_record)
        elif intent_res.primary_intent == AgentIntent.VIDEO_LEARNING or "فيديو" in message.lower() or "محاضرة" in message.lower():
            vid_search = tools.execute_tool("search_video_knowledge", {"query": message})
            trace.tools_executed.append(vid_search)

        # 10. Generate Visual Artifact or Slide Deck if Requested
        visual_artifact = None
        media_type = None
        media_svg = None
        media_title = None

        if intent_res.wants_visual or intent_res.primary_intent == AgentIntent.VISUAL_LEARNING:
            vtype = intent_res.visual_type or "mindmap"
            visual_artifact = generate_educational_visual(
                topic=message,
                visual_type=vtype,
                discipline=intent_res.discipline,
            )
            media_type = "svg"
            media_svg = visual_artifact.svg
            media_title = visual_artifact.title

        slides_deck = None
        if intent_res.wants_slides or intent_res.primary_intent == AgentIntent.SLIDE_PRESENTATION:
            slides_deck = generate_structured_slide_deck(
                topic=message,
                subject_title=subject.name,
                target_slides_count=5,
            )

        # 11. Fetch Active Ingested Agent Skills
        active_skills_db = self.db.scalars(
            select(AgentSkill).where(AgentSkill.is_active == True)
        ).all()
        active_skills_list = [
            {"title": s.title, "system_instructions": s.system_instructions}
            for s in active_skills_db
        ]

        # 12. Build Dynamic Pedagogical Instruction & Assemble Context
        system_instruction = build_dynamic_pedagogical_instruction(
            subject_title=subject.name,
            intent=intent_res,
            skill_level=skill_level,
            learning_style=student_prof.get("learning_style", "balanced"),
            explanation_depth=student_prof.get("explanation_depth", "balanced"),
            active_skills=active_skills_list,
        )

        assembled_context = self.context_selector.assemble_context(
            subject_title=subject.name,
            student_profile=student_prof,
            passages=passages,
            conversation_history=conv_history,
            subject_overview=subject_overview,
            academic_chapters=academic_chapters,
            missing_chapters=missing_chapters,
            prerequisites=prerequisites,
            cross_doc_conflicts=conflicts,
        )

        # 13. Route LLM Request through Existing AI Router
        router_task = map_intent_to_router_task_type(intent_res)
        trace.router_task_type = router_task

        prompt_payload = f"سؤال واستفسار الطالب:\n{message}\n\nسياق ومراجع المادة المعتمدة:\n{assembled_context}"

        raw_answer = ""
        model_used = ""
        if intent_res.primary_intent == AgentIntent.SLIDE_PRESENTATION and slides_deck:
            raw_answer = render_slide_deck_to_markdown(slides_deck)
            model_used = "agent_slide_engine"
        else:
            raw_answer, model_used = execute_llm_request_via_router(
                task_type=router_task,
                prompt=prompt_payload,
                system_instruction=system_instruction,
                db=self.db,
                skill_level=skill_level,
                passages=passages,
            )

        trace.model_used = model_used

        # 14. Quality Filter & Sanitization
        final_answer = sanitize_pedagogical_output(raw_answer)

        # 15. Generate Dynamic Follow-Up Suggestions
        suggested_replies = []
        try:
            suggested_replies = gemini_service.generate_follow_up_suggestions(
                last_answer=final_answer[:1000],
                db=self.db,
            )
        except Exception as exc:
            logger.warning("Could not generate follow-up suggestions: %s", exc)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        trace.duration_ms = round(elapsed_ms, 2)

        # 16. Persist Orchestrator Decision Log
        self._log_decision(subject_id, "study_agent", trace, final_answer, True)

        return AgentRunResult(
            answer=final_answer,
            execution_trace=trace,
            media_type=media_type,
            media_svg=media_svg,
            media_title=media_title,
            slides=slides_deck,
            visual=visual_artifact,
            suggested_replies=suggested_replies,
        )

    def _log_decision(
        self,
        subject_id: UUID | None,
        request_type: str,
        trace: AgentExecutionTrace,
        answer: str,
        success: bool,
    ) -> None:
        """Persist structured decision trace to OrchestratorDecision table."""
        try:
            plan_data = [
                {"tool": t.tool_name, "success": t.success, "time_ms": t.execution_time_ms}
                for t in trace.tools_executed
            ]
            result_data = {
                "model_used": trace.model_used,
                "router_task": trace.router_task_type,
                "answer_preview": answer[:250],
                "duration_ms": trace.duration_ms,
            }
            decision = OrchestratorDecision(
                id=uuid.uuid4(),
                subject_id=subject_id,
                request_type=request_type,
                plan_json=json.dumps(plan_data, ensure_ascii=False),
                result_json=json.dumps(result_data, ensure_ascii=False),
                error_message=None if success else "Agent error",
                success=success,
            )
            self.db.add(decision)
            self.db.flush()
        except Exception as exc:
            logger.warning("Failed to persist agent decision log: %s", exc)
