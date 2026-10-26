from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from google import genai
from google.genai import types
from sqlalchemy import select

from app.core.config import get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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
        "chat_qa": (0.2, 900),
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
                    temperature=base_temp,
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


def safe_call_ai(func: Callable[..., Any], *args: Any, db: Session | None = None, **kwargs: Any) -> Any:
    """Call an AI generator passing db if supported, or without it if monkeypatched in tests."""
    try:
        sig = inspect.signature(func)
        if "db" in sig.parameters or any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
            return func(*args, db=db, **kwargs)
    except Exception:
        pass
    try:
        return func(*args, db=db, **kwargs)
    except TypeError:
        return func(*args, **kwargs)
