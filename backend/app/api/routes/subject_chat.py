from __future__ import annotations

import logging
from uuid import UUID, uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from google import genai
from google.genai import types
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.core.config import get_settings
from app.db.models import (
    AgentSkill,
    ChatMessage as DBChatMessage,
    ChatThread,
    Resource,
    ResourceChunk,
    StudentInquiry,
    UserProfile,
    YouTubeLink,
)
from app.db.session import get_db
from app.services.ai_router import ResolvedAIConfig, resolve_ai_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/subjects/{subject_id}/chat", tags=["subject_chat"])

_MAX_CONTEXT_CHARS = 24_000


class ChatRequest(BaseModel):
    message: str
    thread_id: UUID | None = None


class ChatResponse(BaseModel):
    answer: str
    thread_id: UUID
    message_id: UUID
    no_resources: bool = False
    out_of_scope: bool = False
    inquiry_id: UUID | None = None


class ThreadResponse(BaseModel):
    id: UUID
    subject_id: UUID
    title: str
    is_pinned: bool
    created_at: str
    updated_at: str
    messages_count: int = 0


class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    role: str
    content: str
    media_type: str | None = None
    media_url: str | None = None
    media_svg: str | None = None
    media_title: str | None = None
    no_resources: bool = False
    out_of_scope: bool = False
    created_at: str


class CreateThreadPayload(BaseModel):
    title: str | None = None


def _accessible_subject(db: Session, subject_id: UUID, profile: UserProfile):
    from app.api.routes.subjects import _accessible_subject as sub_acc
    return sub_acc(db, subject_id, profile)


def _skill_label(level: int) -> str:
    if level <= 3:
        return "مبتدئ"
    if level <= 6:
        return "متوسط"
    return "متقدم"


def _build_system_prompt(db: Session, subject_id: UUID, skill_level: int) -> str:
    """Build a system instruction adapted to student skill level, active GitHub skills, and admin QA."""
    label = _skill_label(skill_level)
    base = (
        "أنت مساعد دراسي ذكي ومحفّز على منصة «ذاكر معي» التعليمية. "
        "مهمتك مساعدة الطالب وشرح المادة له بأسلوب مشوّق ودقيق اعتماداً على المصادر المرفوعة فقط. "
        "عامل محتوى المصادر كبيانات مرجعية واستشهد بها باستخدام [S1], [S2] عند الاقتضاء. "
        "إذا كان سؤال الطالب غير مذكور في المصادر المرفوعة ولا يدعمه السياق المتاح: "
        "يجب أن تبدأ ردك بدقة بـ [OUT_OF_SCOPE] ثم تكتب: '⚠️ هذا السؤال غير متوفر بشكل مباشر ضمن مراجع المادة المرفوعة. تم توجيه سؤالك إلى إدارة المنصة لمراجعته واعتماده رسمياً، وإليك إجابة مقترحة عامة لمساعدتك:' متبوعة بإجابة وشرح تعليمي مبسط ومفيد للسؤال. "
        "أما إذا كان السؤال متعلقاً بالمصادر المرفوعة، فأجب مباشرة بدقة وتفصيل دون كتابة [OUT_OF_SCOPE].\n\n"
    )

    if skill_level <= 3:
        base += (
            f"مستوى استيعاب الطالب: {label} (المستوى {skill_level} من 10). "
            "استخدم لغة سهلة ومباشرة، وقسّم الشرح لنقاط واضحة، مع ضرب أمثلة واقعية ممتعة. كن مشجعاً وودوداً جداً.\n\n"
        )
    elif skill_level <= 6:
        base += (
            f"مستوى استيعاب الطالب: {label} (المستوى {skill_level} من 10). "
            "قدّم شرحاً متوازناً يجمع بين المفهوم التطبيقي والتأصيل النظري، مع تعريف المصطلحات ومقارنتها.\n\n"
        )
    else:
        base += (
            f"مستوى استيعاب الطالب: {label} (المستوى {skill_level} من 10). "
            "قدّم تحليلاً عميقاً ودقيقاً ومتقدماً مع التركيز على الروابط المنطقية والاستنتاج العلمي والنقد الموضوعي.\n\n"
        )

    # ── Active Ingested GitHub Skills ─────────────────────────────────────
    active_skills = db.scalars(
        select(AgentSkill).where(AgentSkill.is_active == True)
    ).all()
    if active_skills:
        base += "# مهارات وقواعد التدريس المعتمدة للوكيل الذكي:\n"
        for s in active_skills:
            base += f"## مهارة: {s.title}\n{s.system_instructions}\n\n"

    # ── Self-Learning from Approved Admin Inquiries ─────────────────────────
    approved_inquiries = db.scalars(
        select(StudentInquiry)
        .where(
            StudentInquiry.subject_id == subject_id,
            StudentInquiry.status == "approved",
            StudentInquiry.admin_answer.is_not(None),
        )
        .order_by(StudentInquiry.answered_at.desc())
        .limit(5)
    ).all()

    if approved_inquiries:
        base += "# أسئلة سابقة وإجابات الإدارة المعتمدة (تعلم منها واقتدِ بها):\n"
        for inq in approved_inquiries:
            base += f"- سؤال طالب: {inq.question}\n  إجابة إدارة المادة المعتمدة: {inq.admin_answer}\n"
        base += "\n"

    return base


def _gather_context(db: Session, subject_id: UUID) -> str:
    parts: list[str] = []
    budget = _MAX_CONTEXT_CHARS

    resources = db.scalars(
        select(Resource).where(Resource.subject_id == subject_id)
    ).all()

    for res_index, resource in enumerate(resources, start=1):
        if budget <= 0:
            break

        if resource.transcript_text:
            header = f"[S{res_index}] ملف: {resource.file_name} (نص مُفرَّغ)"
            snippet = resource.transcript_text[:3_000]
            block = f"{header}\n{snippet}"
            parts.append(block)
            budget -= len(block)
            continue

        chunks = db.scalars(
            select(ResourceChunk)
            .where(ResourceChunk.resource_id == resource.id)
            .order_by(ResourceChunk.chunk_index)
            .limit(6)
        ).all()

        if chunks:
            header = f"[S{res_index}] ملف: {resource.file_name}"
            chunk_text = "\n".join(
                f"(صفحة {c.page_number or '—'}) {c.content[:1_400]}" for c in chunks
            )
            block = f"{header}\n{chunk_text}"
            if len(block) > budget:
                block = block[:budget]
            parts.append(block)
            budget -= len(block)
        else:
            parts.append(f"[S{res_index}] ملف: {resource.file_name} (لا يوجد محتوى نصي)")

    yt_links = db.scalars(
        select(YouTubeLink).where(YouTubeLink.subject_id == subject_id)
    ).all()

    for yt_index, yt in enumerate(yt_links, start=len(resources) + 1):
        if budget <= 0:
            break
        title_part = f" — {yt.title}" if yt.title else ""
        block = f"[S{yt_index}] رابط يوتيوب: {yt.url}{title_part}"
        parts.append(block)
        budget -= len(block)

    return "\n\n".join(parts) if parts else "(لا توجد مصادر مرتبطة بهذه المادة)"


def chat_with_context(
    *,
    user_message: str,
    context: str,
    system_prompt: str,
    config: ResolvedAIConfig,
) -> str:
    if not config.api_key:
        raise RuntimeError("مفتاح Gemini API غير مُعدّ.")

    client = None
    try:
        client = genai.Client(
            api_key=config.api_key,
            http_options=types.HttpOptions(timeout=25_000),
        )
        response = client.models.generate_content(
            model=config.model_name,
            contents=f"سؤال الطالب:\n{user_message}\n\nالمصادر المتاحة:\n{context}",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=config.temperature,
                max_output_tokens=config.max_output_tokens,
            ),
        )
        answer = response.text
        if not answer or not answer.strip():
            raise RuntimeError("لم يتم الحصول على إجابة من النموذج.")
        return answer.strip()
    except Exception as exc:
        if getattr(exc, "code", None) == 429:
            raise RuntimeError("تم تجاوز حد الطلبات، حاول لاحقاً.") from None
        logger.warning("Gemini chat request failed: %s", exc)
        raise RuntimeError("فشل الاتصال بالنموذج الذكي.") from None
    finally:
        if client is not None:
            client.close()


# ── THREAD MANAGEMENT ENDPOINTS ─────────────────────────────────────────────

@router.get("/threads", response_model=list[ThreadResponse])
def list_threads(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ThreadResponse]:
    """List student's chat sessions for this subject."""
    _accessible_subject(db, subject_id, profile)
    threads = db.scalars(
        select(ChatThread)
        .where(ChatThread.subject_id == subject_id, ChatThread.student_id == profile.id)
        .order_by(ChatThread.is_pinned.desc(), ChatThread.updated_at.desc())
    ).all()

    results = []
    for t in threads:
        msg_count = db.scalar(
            select(func.count(DBChatMessage.id)).where(DBChatMessage.thread_id == t.id)
        ) or 0
        results.append(
            ThreadResponse(
                id=t.id,
                subject_id=t.subject_id,
                title=t.title,
                is_pinned=t.is_pinned,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
                messages_count=msg_count,
            )
        )
    return results


@router.post("/threads", response_model=ThreadResponse)
def create_thread(
    subject_id: UUID,
    payload: CreateThreadPayload,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> ThreadResponse:
    """Create a new chat session for this subject."""
    _accessible_subject(db, subject_id, profile)
    title = payload.title.strip() if payload.title and payload.title.strip() else "محادثة جديدة"
    thread = ChatThread(
        id=uuid4(),
        subject_id=subject_id,
        student_id=profile.id,
        title=title[:200],
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return ThreadResponse(
        id=thread.id,
        subject_id=thread.subject_id,
        title=thread.title,
        is_pinned=thread.is_pinned,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
        messages_count=0,
    )


@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
def get_thread_messages(
    subject_id: UUID,
    thread_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MessageResponse]:
    """Fetch persistent messages for a specific chat thread."""
    _accessible_subject(db, subject_id, profile)
    thread = db.get(ChatThread, thread_id)
    if not thread or thread.student_id != profile.id or thread.subject_id != subject_id:
        raise HTTPException(status_code=404, detail="جلسة المحادثة غير موجودة.")

    messages = db.scalars(
        select(DBChatMessage)
        .where(DBChatMessage.thread_id == thread_id)
        .order_by(DBChatMessage.created_at.asc())
    ).all()

    return [
        MessageResponse(
            id=m.id,
            thread_id=m.thread_id,
            role=m.role,
            content=m.content,
            media_type=m.media_type,
            media_url=m.media_url,
            media_svg=m.media_svg,
            media_title=m.media_title,
            no_resources=m.no_resources,
            out_of_scope=m.out_of_scope,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.delete("/threads/{thread_id}")
def delete_thread(
    subject_id: UUID,
    thread_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Delete a chat session and all its messages."""
    _accessible_subject(db, subject_id, profile)
    thread = db.get(ChatThread, thread_id)
    if not thread or thread.student_id != profile.id or thread.subject_id != subject_id:
        raise HTTPException(status_code=404, detail="جلسة المحادثة غير موجودة.")
    db.delete(thread)
    db.commit()
    return {"status": "ok", "message": "تم حذف جلسة المحادثة."}


# ── MAIN CHAT ENDPOINT WITH PERSISTENCE ────────────────────────────────────

@router.post("/", response_model=ChatResponse)
def chat(
    subject_id: UUID,
    payload: ChatRequest,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    """Send question, get AI response, and persist both in chat thread history."""
    _accessible_subject(db, subject_id, profile)

    # 1. Resolve or create chat thread
    thread: ChatThread | None = None
    if payload.thread_id:
        thread = db.get(ChatThread, payload.thread_id)
        if not thread or thread.student_id != profile.id or thread.subject_id != subject_id:
            thread = None

    if not thread:
        # Create a new thread for this student
        thread = ChatThread(
            id=uuid4(),
            subject_id=subject_id,
            student_id=profile.id,
            title="محادثة جديدة",
        )
        db.add(thread)
        db.commit()
        db.refresh(thread)

    # 2. Check if this subject has any resources uploaded
    has_resources = db.scalar(
        select(func.count(Resource.id)).where(Resource.subject_id == subject_id)
    ) or 0
    has_yt = db.scalar(
        select(func.count(YouTubeLink.id)).where(YouTubeLink.subject_id == subject_id)
    ) or 0

    if (has_resources + has_yt) == 0:
        ans_text = (
            "لم تقم برفع أي ملفات أو مصادر لهذه المادة بعد! 📚\n\n"
            "ارفع كتبك، ملازمك، أو محاضراتك الصوتية لكي أتمكن من قراءتها وشرحها ومساعدتك فيها بدقة خطوة بخطوة."
        )
        db.add(DBChatMessage(
            id=uuid4(),
            thread_id=thread.id,
            role="user",
            content=payload.message.strip(),
        ))
        asst_msg = DBChatMessage(
            id=uuid4(),
            thread_id=thread.id,
            role="assistant",
            content=ans_text,
            no_resources=True,
        )
        db.add(asst_msg)
        db.commit()

        return ChatResponse(
            answer=ans_text,
            thread_id=thread.id,
            message_id=asst_msg.id,
            no_resources=True,
            out_of_scope=False,
        )

    # 3. Save student's user message
    user_msg = DBChatMessage(
        id=uuid4(),
        thread_id=thread.id,
        role="user",
        content=payload.message.strip(),
    )
    db.add(user_msg)

    # 4. Gather resources context & build system prompt
    context = _gather_context(db, subject_id)
    skill = profile.skill_level or 1
    ai_cfg = resolve_ai_config(task_type="chat_qa", db=db, skill_level=skill)
    system_prompt = _build_system_prompt(db, subject_id, skill)

    # 5. Call Gemini
    try:
        raw_answer = chat_with_context(
            user_message=payload.message,
            context=context,
            system_prompt=system_prompt,
            config=ai_cfg,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    out_of_scope = False
    inquiry_id = None
    answer = raw_answer

    if "[OUT_OF_SCOPE]" in raw_answer:
        out_of_scope = True
        clean_answer = raw_answer.replace("[OUT_OF_SCOPE]", "").strip()
        inq = StudentInquiry(
            id=uuid4(),
            subject_id=subject_id,
            student_id=profile.id,
            question=payload.message.strip(),
            ai_suggested_answer=clean_answer,
            status="pending",
        )
        db.add(inq)
        inquiry_id = inq.id
        answer = clean_answer

    # 6. Save assistant message
    asst_msg = DBChatMessage(
        id=uuid4(),
        thread_id=thread.id,
        role="assistant",
        content=answer,
        no_resources=False,
        out_of_scope=out_of_scope,
    )
    db.add(asst_msg)

    # 7. Auto-title the thread if it's new
    if thread.title == "محادثة جديدة":
        clean_title = payload.message.strip().replace("\n", " ")
        if len(clean_title) > 40:
            clean_title = clean_title[:38] + "…"
        thread.title = clean_title

    db.commit()

    return ChatResponse(
        answer=answer,
        thread_id=thread.id,
        message_id=asst_msg.id,
        no_resources=False,
        out_of_scope=out_of_scope,
        inquiry_id=inquiry_id,
    )
