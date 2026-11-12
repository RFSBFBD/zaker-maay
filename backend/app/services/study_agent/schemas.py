from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentIntent(str, Enum):
    RETRIEVAL = "retrieval"
    EXPLANATION = "explanation"
    DEEP_EXPLANATION = "deep_explanation"
    PROBLEM_SOLVING = "problem_solving"
    BRAINSTORMING = "brainstorming"
    SUMMARIZATION = "summarization"
    EXAM_PREPARATION = "exam_preparation"
    KNOWLEDGE_ASSESSMENT = "knowledge_assessment"
    REVISION = "revision"
    VISUAL_LEARNING = "visual_learning"
    VIDEO_LEARNING = "video_learning"
    SLIDE_PRESENTATION = "slide_presentation"
    CONVERSATION = "conversation"
    ADMINISTRATIVE = "administrative"


class DisciplineDomain(str, Enum):
    COMPUTER_SCIENCE = "computer_science"
    MATHEMATICS = "mathematics"
    NATURAL_SCIENCES = "natural_sciences"
    HUMANITIES = "humanities"
    GENERAL = "general"


class ComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LearningStyle(str, Enum):
    BALANCED = "balanced"
    VISUAL = "visual"
    CONCEPTUAL = "conceptual"
    PRACTICAL = "practical"
    STEP_BY_STEP = "step_by_step"


class ExplanationDepth(str, Enum):
    CONCISE = "concise"
    BALANCED = "balanced"
    DEEP_12_STEP = "deep_12_step"


class IntentAnalysisResult(BaseModel):
    primary_intent: AgentIntent
    secondary_intents: list[AgentIntent] = Field(default_factory=list)
    discipline: DisciplineDomain = DisciplineDomain.GENERAL
    complexity: ComplexityLevel = ComplexityLevel.MEDIUM
    requires_tools: bool = True
    requires_rag: bool = True
    wants_visual: bool = False
    visual_type: str | None = None
    wants_slides: bool = False
    expected_outcome: str = ""
    is_administrative: bool = False


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


class ExecutionStepPlan(BaseModel):
    step_id: int
    action: str
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class SlideItem(BaseModel):
    slide_number: int
    title: str
    subtitle: str | None = None
    bullet_points: list[str] = Field(default_factory=list)
    key_formula_or_code: str | None = None
    presenter_notes: str | None = None
    visual_suggestion: str | None = None


class SlideDeck(BaseModel):
    topic: str
    target_audience: str
    total_slides: int
    slides: list[SlideItem]
    closing_summary: str | None = None


class VisualArtifact(BaseModel):
    visual_type: str  # mindmap, flowchart, memory_layout, comparison, architecture, svg
    title: str
    svg: str | None = None
    mermaid_spec: str | None = None
    description: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    connections: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeUpdateEvidence(BaseModel):
    evidence_type: str  # student_solved_problem, student_correct_quiz, student_articulated_explanation, student_misconception_demonstrated
    topic_name: str
    delta_mastery: int = 0
    delta_confidence: int = 0
    new_understood_concepts: list[str] = Field(default_factory=list)
    new_misconceptions: list[str] = Field(default_factory=list)
    notes: str = ""


class AgentExecutionTrace(BaseModel):
    request_id: str
    student_id: str
    subject_id: str
    user_message: str
    intent: IntentAnalysisResult
    plan: list[ExecutionStepPlan] = Field(default_factory=list)
    tools_executed: list[ToolCallRecord] = Field(default_factory=list)
    model_requested: str = ""
    model_used: str = ""
    router_task_type: str = ""
    evidence_recorded: list[KnowledgeUpdateEvidence] = Field(default_factory=list)
    duration_ms: float = 0.0
    quality_checks_passed: bool = True


@dataclass
class AgentRunResult:
    answer: str
    execution_trace: AgentExecutionTrace
    media_type: str | None = None
    media_url: str | None = None
    media_svg: str | None = None
    media_title: str | None = None
    slides: SlideDeck | None = None
    visual: VisualArtifact | None = None
    no_resources: bool = False
    out_of_scope: bool = False
    suggested_replies: list[str] = field(default_factory=list)
