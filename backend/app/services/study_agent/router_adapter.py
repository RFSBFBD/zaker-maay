from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.services.ai_router import (
    ResolvedAIConfig,
    resolve_ai_config,
    resolve_fallback_model,
    safe_call_ai,
)
from app.services import gemini as gemini_service
from app.services.study_agent.schemas import AgentIntent, IntentAnalysisResult

logger = logging.getLogger(__name__)


def map_intent_to_router_task_type(intent: IntentAnalysisResult) -> str:
    """Map high-level Agent intent to existing AI Router task_type."""
    if intent.primary_intent == AgentIntent.VISUAL_LEARNING and not intent.wants_slides:
        return "image_generation"
    if intent.primary_intent == AgentIntent.EXAM_PREPARATION:
        return "quiz_generation"
    if intent.primary_intent == AgentIntent.REVISION:
        return "flashcards"
    if intent.primary_intent in (AgentIntent.DEEP_EXPLANATION, AgentIntent.SLIDE_PRESENTATION):
        return "document_ai"
    return "chat_qa"


def execute_llm_request_via_router(
    *,
    task_type: str,
    prompt: str,
    system_instruction: str,
    db: Session,
    skill_level: int = 1,
    passages: list | None = None,
    temperature_override: float | None = None,
    max_tokens_override: int | None = None,
) -> tuple[str, str]:
    """Execute LLM generation by instructing the existing AI Router and honoring configured models and fallbacks.
    
    Returns (response_text, model_name_used).
    """
    config = resolve_ai_config(
        task_type=task_type,
        db=db,
        skill_level=skill_level,
    )

    if task_type == "chat_qa":
        # Route through canonical grounded generator respecting mock and fallback hooks
        text = safe_call_ai(
            gemini_service.generate_grounded_answer,
            prompt,
            passages=passages or [],
            system_prompt=system_instruction,
            db=db,
            _ai_config=config,
        )
        return text, config.model_name

    if not config.api_key:
        raise gemini_service.GeminiNotConfigured("Gemini API key is not configured")

    temp = temperature_override if temperature_override is not None else config.temperature
    tokens = max_tokens_override if max_tokens_override is not None else max(config.max_output_tokens, 2048)

    models_to_try = [config.model_name]
    fallback = resolve_fallback_model(task_type, db=db)
    if fallback and fallback != config.model_name:
        models_to_try.append(fallback)

    last_exc = None
    for model_name in models_to_try:
        client = None
        try:
            client = genai.Client(
                api_key=config.api_key,
                http_options=types.HttpOptions(timeout=30_000),
            )
            logger.info("Directing AI Router request to model: %s (task: %s)", model_name, task_type)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temp,
                    max_output_tokens=tokens,
                    thinking_config=types.ThinkingConfig(thinking_level="minimal"),
                ),
            )
            text = response.text
            if text and text.strip():
                return text.strip(), model_name
            raise gemini_service.GeminiRequestFailed("Empty response from model")
        except Exception as exc:
            last_exc = exc
            logger.warning("Model %s failed for task %s: %s", model_name, task_type, exc)
            if getattr(exc, "code", None) == 429:
                raise gemini_service.GeminiRateLimited from exc
            continue
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    if isinstance(last_exc, gemini_service.GeminiRateLimited):
        raise last_exc
    if isinstance(last_exc, gemini_service.GeminiNotConfigured):
        raise last_exc
    raise gemini_service.GeminiRequestFailed(f"All configured models failed for task {task_type}: {last_exc}") from last_exc
