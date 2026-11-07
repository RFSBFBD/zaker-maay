"""Agent Orchestrator — planning layer between API endpoints and Gemini model calls.

The orchestrator receives a request, classifies its intent, builds an ordered
plan of sub-tasks, executes each step using the existing AI service functions,
retries failed steps with a configured fallback model when available, and logs
the full decision trace for admin review.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

import sys
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIModelConfig, OrchestratorDecision
from app.services.ai_router import ResolvedAIConfig, resolve_ai_config, classify_agent_intent

logger = logging.getLogger(__name__)


# ── Plan step dataclasses ────────────────────────────────────────────────────

@dataclass
class PlanStep:
    """A single step in an orchestrated plan."""
    task_type: str
    description: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    model_name: str = "unknown"


@dataclass
class OrchestratorResult:
    """The combined result of executing an orchestration plan."""
    success: bool
    plan: list[dict]
    results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    decision_id: UUID | None = None


# ── Intent classifier ────────────────────────────────────────────────────────

def classify_intent(message: str) -> list[str]:
    """Classify user message into one or more task types using intelligent agent classification."""
    return classify_agent_intent(message)


def build_plan(intents: list[str], **kwargs: Any) -> list[PlanStep]:
    """Build an ordered plan from classified intents."""
    plan = []
    for intent in intents:
        if intent == "chat_qa":
            plan.append(PlanStep(
                task_type="chat_qa",
                description="Generate text answer from subject sources",
                kwargs={
                    "question": kwargs.get("message", ""),
                    "passages": kwargs.get("passages", []),
                    "system_prompt": kwargs.get("system_prompt"),
                },
            ))
        elif intent == "image_generation":
            plan.append(PlanStep(
                task_type="image_generation",
                description="Generate educational illustration",
                kwargs={
                    "prompt": kwargs.get("message", ""),
                    "context": kwargs.get("context", ""),
                },
            ))
        elif intent == "quiz_generation":
            plan.append(PlanStep(
                task_type="quiz_generation",
                description="Generate MCQ quiz from subject sources",
                kwargs={
                    "passages": kwargs.get("passages", []),
                },
            ))
        elif intent == "flashcards":
            plan.append(PlanStep(
                task_type="flashcards",
                description="Generate flashcard set from subject sources",
                kwargs={
                    "passages": kwargs.get("passages", []),
                },
            ))
    return plan


# ── Step executor with fallback ─────────────────────────────────────────────

def _get_executor(task_type: str) -> Callable[..., Any]:
    """Get the executor for a task type by looking up the module dynamically."""
    from app.services import gemini
    executors = {
        "chat_qa": gemini.generate_grounded_answer,
        "image_generation": gemini.generate_concept_illustration,
        "quiz_generation": gemini.generate_quiz_draft,
        "flashcards": gemini.generate_flashcard_draft,
    }
    func = executors.get(task_type)
    if func is None:
        raise ValueError(f"No executor registered for task type: {task_type}")
    return func


def _resolve_model(task_type: str, db: Session | None, *, use_fallback: bool) -> ResolvedAIConfig:
    """Resolve the AI config for a task, using fallback_model if requested and available."""
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    cfg = resolve_ai_config(task_type, db=db)
    if not use_fallback:
        return cfg
    if db is not None:
        row = db.scalar(
            select(AIModelConfig).where(
                AIModelConfig.task_type == task_type,
                AIModelConfig.fallback_model.is_not(None),
            )
        )
        if row and row.fallback_model:
            logger.info("[orchestrator] Using fallback model %s for %s", row.fallback_model, task_type)
            cfg = resolve_ai_config(
                task_type, db=db,
                default_model=row.fallback_model,
                default_key=row.api_key or settings.gemini_api_key,
            )
    return cfg


def _execute_step(
    step: PlanStep,
    db: Session,
    *,
    use_fallback: bool = False,
) -> dict[str, Any]:
    """Execute a single plan step, with optional fallback model on failure."""
    func = _get_executor(step.task_type)

    extra_kwargs: dict[str, Any] = dict(step.kwargs)
    cfg = _resolve_model(step.task_type, db, use_fallback=use_fallback)
    extra_kwargs["_ai_config"] = cfg

    start_time = time.time()
    logger.info(
        "[orchestrator] Executing step: %s (model=%s) %s",
        step.task_type,
        cfg.model_name,
        step.description,
    )

    try:
        result = func(*step.args, db=db, **extra_kwargs)
        elapsed = time.time() - start_time
        logger.info(
            "[orchestrator] Step %s completed in %.2fs",
            step.task_type,
            elapsed,
        )
        return {
            "success": True,
            "result": result,
            "elapsed_sec": round(elapsed, 2),
            "step_type": step.task_type,
            "model_used": cfg.model_name,
        }
    except Exception as exc:
        elapsed = time.time() - start_time
        # Fatal errors: don't retry, re-raise immediately
        if isinstance(exc, (
            __import__("app.services.gemini", fromlist=["GeminiNotConfigured"]).GeminiNotConfigured,
            __import__("app.services.gemini", fromlist=["GeminiRateLimited"]).GeminiRateLimited,
            
        )):
            raise
        if not use_fallback:
            return _execute_step(step, db, use_fallback=True)
        logger.warning(
            "[orchestrator] Step %s failed after %.2fs: %s",
            step.task_type,
            elapsed,
            exc,
        )
        return {
            "success": False,
            "error": str(exc),
            "elapsed_sec": round(elapsed, 2),
            "step_type": step.task_type,
            "model_used": cfg.model_name,
        }


import sys

# ── Main orchestration entry points ──────────────────────────────────────────

def orchestrate_chat(
    message: str,
    subject_id: UUID,
    db: Session,
    passages: list | None = None,
    system_prompt: str | None = None,
    context: str | None = None,
) -> OrchestratorResult:
    """Orchestrate a chat request: classify intent, build plan, execute steps."""
    intents = classify_intent(message)
    plan = build_plan(
        intents,
        message=message,
        passages=passages or [],
        system_prompt=system_prompt,
        context=context or "",
    )

    plan_json = json.dumps([
        {"task_type": s.task_type, "description": s.description}
        for s in plan
    ], ensure_ascii=False)

    logger.info(
        "[orchestrator] Chat request classified: intents=%s, plan_steps=%d",
        intents,
        len(plan),
    )

    results: dict[str, Any] = {}
    plan_log: list[dict] = []
    start_time = time.time()

    for step in plan:
        step_start = time.time()
        step_result = _execute_step(step, db)
        step_elapsed = time.time() - step_start
        plan_log.append({
            "step": step.task_type,
            "description": step.description,
            "success": step_result["success"],
            "elapsed_sec": step_result.get("elapsed_sec", 0),
            "model_used": step_result.get("model_used", "unknown"),
            "error": step_result.get("error"),
        })
        if step_result["success"]:
            results[step.task_type] = step_result["result"]
        else:
            logger.error("[orchestrator] Step failed: %s", step.task_type)

    total_elapsed = time.time() - start_time
    # If chat_qa succeeded, the user gets their logical answer even if image generation had an issue
    if "chat_qa" in [s.task_type for s in plan]:
        overall_success = "chat_qa" in results
    else:
        overall_success = any(s["success"] for s in plan_log) if plan_log else True

    _log_decision(db, subject_id, "chat", plan_json, results, plan_log, overall_success)

    logger.info(
        "[orchestrator] Chat orchestration completed: success=%s, steps=%d, elapsed=%.2fs",
        overall_success,
        len(plan),
        total_elapsed,
    )

    return OrchestratorResult(
        success=overall_success,
        plan=plan_log,
        results=results,
        error=None if overall_success else "Orchestration failed",
        decision_id=None,
    )


def _log_decision(
    db: Session,
    subject_id: UUID | None,
    request_type: str,
    plan_json: str,
    results: dict,
    plan_log: list[dict],
    success: bool,
) -> None:
    """Persist an OrchestratorDecision record."""
    decision = OrchestratorDecision(
        id=uuid.uuid4(),
        subject_id=subject_id,
        request_type=request_type,
        plan_json=plan_json,
        result_json=json.dumps(results, default=str, ensure_ascii=False) if results else None,
        error_message=None if success else "One or more steps failed",
        success=success,
    )
    db.add(decision)
    try:
        db.flush()
    except Exception:
        logger.warning("[orchestrator] Failed to persist decision log")


def orchestrate_quiz(
    subject_id: UUID,
    db: Session,
    passages: list | None = None,
) -> OrchestratorResult:
    """Orchestrate quiz generation request."""
    intents = ["quiz_generation"]
    plan = build_plan(intents, passages=passages or [])

    plan_json = json.dumps([
        {"task_type": s.task_type, "description": s.description}
        for s in plan
    ], ensure_ascii=False)

    logger.info("[orchestrator] Quiz request: plan_steps=%d", len(plan))

    results: dict[str, Any] = {}
    plan_log: list[dict] = []
    start_time = time.time()

    for step in plan:
        step_start = time.time()
        step_result = _execute_step(step, db)
        step_elapsed = time.time() - step_start
        plan_log.append({
            "step": step.task_type,
            "description": step.description,
            "success": step_result["success"],
            "elapsed_sec": step_result.get("elapsed_sec", 0),
            "model_used": step_result.get("model_used", "unknown"),
            "error": step_result.get("error"),
        })
        if step_result["success"]:
            results[step.task_type] = step_result["result"]

    total_elapsed = time.time() - start_time
    overall_success = all(s["success"] for s in plan_log)

    _log_decision(db, subject_id, "quiz", plan_json, results, plan_log, overall_success)

    logger.info(
        "[orchestrator] Quiz orchestration completed: success=%s, elapsed=%.2fs",
        overall_success,
        total_elapsed,
    )

    return OrchestratorResult(
        success=overall_success,
        plan=plan_log,
        results=results,
        error=None if overall_success else "Orchestration failed",
        decision_id=None,
    )


def orchestrate_flashcards(
    subject_id: UUID,
    db: Session,
    passages: list | None = None,
) -> OrchestratorResult:
    """Orchestrate flashcard generation request."""
    intents = ["flashcards"]
    plan = build_plan(intents, passages=passages or [])

    plan_json = json.dumps([
        {"task_type": s.task_type, "description": s.description}
        for s in plan
    ], ensure_ascii=False)

    logger.info("[orchestrator] Flashcard request: plan_steps=%d", len(plan))

    results: dict[str, Any] = {}
    plan_log: list[dict] = []
    start_time = time.time()

    for step in plan:
        step_start = time.time()
        step_result = _execute_step(step, db)
        step_elapsed = time.time() - step_start
        plan_log.append({
            "step": step.task_type,
            "description": step.description,
            "success": step_result["success"],
            "elapsed_sec": step_result.get("elapsed_sec", 0),
            "model_used": step_result.get("model_used", "unknown"),
            "error": step_result.get("error"),
        })
        if step_result["success"]:
            results[step.task_type] = step_result["result"]

    total_elapsed = time.time() - start_time
    overall_success = all(s["success"] for s in plan_log)

    _log_decision(db, subject_id, "flashcards", plan_json, results, plan_log, overall_success)

    logger.info(
        "[orchestrator] Flashcard orchestration completed: success=%s, elapsed=%.2fs",
        overall_success,
        total_elapsed,
    )

    return OrchestratorResult(
        success=overall_success,
        plan=plan_log,
        results=results,
        error=None if overall_success else "Orchestration failed",
        decision_id=None,
    )
