from __future__ import annotations

import inspect
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from google import genai
from google.genai import types
from sqlalchemy import select

from app.core.config import get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Agent Intent Regex Patterns ──────────────────────────────────────────────

_IMAGE_ACTION_PATTERNS = [
    r"\b(و|ف)?(ارسم|ارسم\s*(لي|لنا|ليا|لى))\b",
    r"\b(انشئ|أنشئ|ولد|توليد|صمم|اعمل|اصنع)(\s*(لي|لنا|ليا|لى))?\s+(صورة|صوره|رسمة|رسمه|مخطط|رسم\s+بياني|دياجرام)\b",
    r"\b(عايز|اريد|أريد|محتاج)(\s*(لي|لنا|ليا|لى))?\s+(صورة|صوره|رسمة|رسمه|مخطط|رسم\s+توضيحي)\b",
    r"\b(مخطط\s+بياني|رسم\s+توضيحي\s+لـ|رسمة\s+لـ|صورة\s+لـ)\b",
    r"\b(draw|sketch|illustrate)\b",
    r"\b(generate|create|make|produce)\s+(an?\s+)?(image|picture|diagram|illustration|visual)\b",
    r"\b(diagram\s+of|schema\s+of|visualize|infographic)\b",
    r"\b(diagram|image)\b",
]

_QUIZ_ACTION_PATTERNS = [
    r"\b(و|ف)?(اختبر|اختبرني|اختبرنا|امتحني|امتحان|كويز|كويزات|أسئلة|اسئلة)\b",
    r"\b(quiz|test\s+me|give\s+me\s+a\s+test|exam)\b",
]

_FLASHCARD_ACTION_PATTERNS = [
    r"\b(بطاقات|بطاقة|فلاش\s*كارد|فلاش\s*كاردز|كروت\s+استذكار|مذكرات\s+سريعة)\b",
    r"\b(flashcards?|flash-cards?|study\s+cards?)\b",
]


def classify_agent_intent(message: str) -> list[str]:
    """Agentic intent classification that understands semantics and avoids false positives.
    
    Prevents misrouting of normal inquiries that contain words like:
    'بشكل عام', 'بشكل لوجيك', 'مثال توضيحي', 'صورة عامة', 'هل الرسم مقرر؟'.
    """
    msg_clean = message.strip()
    msg_lower = msg_clean.lower()
    if not msg_clean:
        return ["chat_qa"]

    intents: list[str] = ["chat_qa"]

    # 1. Image / Diagram intent
    wants_img = False
    if msg_lower in ("draw", "رسم", "ارسم", "image", "diagram"):
        wants_img = True
    elif any(re.search(pat, msg_lower, re.IGNORECASE) for pat in _IMAGE_ACTION_PATTERNS):
        wants_img = True

    if wants_img and "image_generation" not in intents:
        intents.append("image_generation")

    # 2. Quiz intent
    wants_quiz = any(re.search(pat, msg_lower, re.IGNORECASE) for pat in _QUIZ_ACTION_PATTERNS)
    if wants_quiz and "quiz_generation" not in intents:
        intents.append("quiz_generation")

    # 3. Flashcard intent
    wants_flashcard = any(re.search(pat, msg_lower, re.IGNORECASE) for pat in _FLASHCARD_ACTION_PATTERNS)
    if wants_flashcard and "flashcards" not in intents:
        intents.append("flashcards")

    return intents

SUPPORTED_TASK_TYPES = {
    "chat_qa": "أسئلة ومساعد المذاكرة الموثق",
    "quiz_generation": "توليد اختبارات MCQ",
    "flashcards": "بطاقات الاستذكار السريعة",
    "concept_map": "خرائط المفاهيم وشبكة العلاقات",
    "study_notes": "الملخصات والمذكرات الموسعة",
    "audio_transcription": "تفريغ المحاضرات الصوتية الذكي",
    "image_generation": "توليد الصور والرسوم التوضيحية (نانو بنانا / Imagen)",
    "document_ai": "التحليل والاستيعاب الذكي للكتب والمستندات",
    "default": "النموذج الافتراضي الاحتياطي",
}


@dataclass
class ResolvedAIConfig:
    task_type: str
    model_name: str
    api_key: str
    temperature: float
    max_output_tokens: int


def resolve_ai_config(
    task_type: str,
    db: Session | None = None,
    default_model: str | None = None,
    default_key: str | None = None,
    skill_level: int = 1,
) -> ResolvedAIConfig:
    """Resolve model, API key, and parameters for a task, prioritizing DB configs when available.

    The ``skill_level`` parameter (1-10) adjusts temperature and, for advanced
    students, may prefer a more capable model:
    * 1-3 (beginner) → higher temperature (0.3) for friendlier, more explanatory responses
    * 4-6 (intermediate) → default temperature for the task
    * 7-10 (advanced) → lower temperature (0.1) and prefer ``gemini-2.5-flash`` if available
    """
    settings = get_settings()
    base_default_key = default_key if default_key is not None else (settings.gemini_api_key or "")
    base_default_model = default_model if default_model is not None else (settings.gemini_model or "gemini-3.5-flash")

    defaults: dict[str, tuple[float, int]] = {
        "chat_qa": (0.2, 2048),
        "quiz_generation": (0.2, 1800),
        "flashcards": (0.2, 3000),
        "concept_map": (0.2, 3000),
        "study_notes": (0.2, 7000),
        "audio_transcription": (0.0, 10000),
        "image_generation": (0.0, 1024),
        "document_ai": (0.1, 4000),
        "default": (0.2, 2000),
    }

    base_temp, base_tokens = defaults.get(task_type, (0.2, 2000))

    # ── Skill-level adjustments ──────────────────────────────────────
    skill_level = max(1, min(skill_level, 10))
    if skill_level <= 3:
        # Beginner: slightly higher temperature for friendlier responses
        base_temp = 0.3
    elif skill_level >= 7:
        # Advanced: lower temperature for precision
        base_temp = 0.1
        if not base_default_model:
            base_default_model = "gemini-3.5-flash"

    if db is not None:
        try:
            from app.db.models import AIModelConfig

            config = db.scalar(
                select(AIModelConfig).where(
                    AIModelConfig.task_type == task_type,
                    AIModelConfig.is_active.is_(True),
                )
            )
            if config is None:
                config = db.scalar(
                    select(AIModelConfig).where(
                        AIModelConfig.task_type == "default",
                        AIModelConfig.is_active.is_(True),
                    )
                )

            if config is not None:
                resolved_model = config.model_name or base_default_model
                if resolved_model in ("gemini-2.5-flash", "gemini-3.8-flash"):
                    resolved_model = "gemini-3.5-flash"
                return ResolvedAIConfig(
                    task_type=task_type,
                    model_name=resolved_model,
                    api_key=config.api_key or base_default_key,
                    temperature=config.temperature if config.temperature is not None else base_temp,
                    max_output_tokens=config.max_output_tokens or base_tokens,
                )
        except Exception as exc:
            logger.warning("Could not read dynamic AIModelConfig from DB, using defaults: %s", exc)

    return ResolvedAIConfig(
        task_type=task_type,
        model_name=base_default_model,
        api_key=base_default_key,
        temperature=base_temp,
        max_output_tokens=base_tokens,
    )




def resolve_fallback_model(task_type: str, db: Session | None = None) -> str | None:
    """Return configured fallback model name for a task if active and present."""
    if db is None:
        return None
    try:
        from app.db.models import AIModelConfig

        row = db.scalar(
            select(AIModelConfig).where(
                AIModelConfig.task_type == task_type,
                AIModelConfig.is_active.is_(True),
                AIModelConfig.fallback_model.is_not(None),
            )
        )
        if row and row.fallback_model and row.fallback_model.strip():
            return row.fallback_model.strip()
    except Exception as exc:
        logger.warning("Could not read fallback model for %s: %s", task_type, exc)
    return None

def safe_call_ai(func: Callable[..., Any], *args: Any, db: Session | None = None, **kwargs: Any) -> Any:
    """Call an AI generator passing db if supported, or without it if monkeypatched in tests."""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        # If introspection is unavailable, make a single compatible attempt;
        # never retry a provider call after it may already have started.
        return func(*args, db=db, **kwargs)

    accepts_db = "db" in sig.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in sig.parameters.values()
    )
    if accepts_db:
        kwargs = {**kwargs, "db": db}
    return func(*args, **kwargs)
