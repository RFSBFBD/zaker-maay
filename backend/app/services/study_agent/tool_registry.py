from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import String, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ChatMessage,
    ChatThread,
    Resource,
    ResourceChunk,
    Subject,
    SubjectMembership,
    UserProfile,
    YouTubeChunk,
    YouTubeLink,
)
from app.services.retrieval import retrieve_for_subject
from app.services.study_agent.learning_service import (
    get_or_create_learning_profile,
    get_topic_knowledge_state,
    list_recent_weak_areas,
    record_student_learning_evidence,
)
from app.services.study_agent.schemas import ToolCallRecord

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    pass


class TenantAccessDenied(Exception):
    pass


class ToolRegistry:
    """MCP-compatible tool registry with strict tenant isolation and bounded execution."""

    def __init__(self, db: Session, student_id: UUID, subject_id: UUID):
        self.db = db
        self.student_id = student_id
        self.subject_id = subject_id
        self._cache: dict[str, Any] = {}
        self._call_count = 0
        self.max_calls = 8
        self._verify_tenant_access()

    def _verify_tenant_access(self) -> None:
        """Enforce tenant isolation: student must be authorized for this subject."""
        subject = self.db.get(Subject, self.subject_id)
        if not subject or subject.archived_at is not None:
            raise TenantAccessDenied("المادة الدراسية غير متوفرة أو تمت أرشفتها.")

        # Check membership or ownership
        if subject.created_by == self.student_id:
            return

        is_member = self.db.scalar(
            select(func.count(SubjectMembership.user_id)).where(
                SubjectMembership.subject_id == self.subject_id,
                SubjectMembership.user_id == self.student_id,
            )
        )
        if not is_member:
            raise TenantAccessDenied("الطالب غير مسجل في هذه المادة الدراسية.")

    def _cache_key(self, tool_name: str, args: dict[str, Any]) -> str:
        serialized = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(f"{tool_name}:{serialized}".encode("utf-8")).hexdigest()

    def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolCallRecord:
        """Execute a tool with iteration bounds, deduplication, and error isolation."""
        self._call_count += 1
        if self._call_count > self.max_calls:
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                success=False,
                error=f"Exceeded maximum tool execution iterations ({self.max_calls})",
            )

        ckey = self._cache_key(tool_name, arguments)
        if ckey in self._cache:
            logger.info("Serving tool result from deduplication cache: %s", tool_name)
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                success=True,
                result=self._cache[ckey],
                execution_time_ms=0.1,
            )

        handler = getattr(self, f"_tool_{tool_name}", None)
        if not handler or not callable(handler):
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                success=False,
                error=f"Tool '{tool_name}' is not registered in AI Study Agent toolset",
            )

        start_t = time.perf_counter()
        try:
            result = handler(**arguments)
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            self._cache[ckey] = result
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                success=True,
                result=result,
                execution_time_ms=round(elapsed_ms, 2),
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            logger.warning("Tool execution error in %s: %s", tool_name, exc)
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                success=False,
                error=str(exc),
                execution_time_ms=round(elapsed_ms, 2),
            )

    # ── Registered Tools ─────────────────────────────────────────────────────

    def _tool_get_student_learning_context(self) -> dict[str, Any]:
        """Fetch the student's learning profile, preferred explanation depth, and weak areas."""
        profile = get_or_create_learning_profile(self.student_id, self.db)
        user = self.db.get(UserProfile, self.student_id)
        skill_level = user.skill_level if user else 1
        weak_areas = list_recent_weak_areas(self.student_id, self.subject_id, self.db, limit=5)

        return {
            "skill_level": skill_level,
            "learning_style": profile.learning_style,
            "explanation_depth": profile.explanation_depth,
            "preferred_language": profile.preferred_language,
            "visual_preference": profile.visual_preference,
            "weak_areas": weak_areas,
        }

    def _tool_search_subject_resources(self, query: str, limit: int = 5) -> dict[str, Any]:
        """Retrieve relevant grounded passages from subject files and transcripts."""
        passages = retrieve_for_subject(
            self.db,
            subject_id=self.subject_id,
            query=query,
            limit=min(limit, 8),
        )
        return {
            "query": query,
            "passages_count": len(passages),
            "passages": [
                {
                    "source_id": f"S{idx}",
                    "resource_id": str(p.resource_id),
                    "file_name": p.file_name,
                    "page_number": p.page_number,
                    "content": p.content,
                }
                for idx, p in enumerate(passages, start=1)
            ],
        }

    def _tool_get_subject_resources_overview(self) -> dict[str, Any]:
        """Get an inventory of all available course documents, books, and lecture videos."""
        subject = self.db.get(Subject, self.subject_id)
        resources = self.db.scalars(
            select(Resource).where(Resource.subject_id == self.subject_id)
        ).all()
        yt_links = self.db.scalars(
            select(YouTubeLink).where(YouTubeLink.subject_id == self.subject_id)
        ).all()

        return {
            "subject_title": subject.name if subject else "",
            "total_documents": len(resources),
            "total_videos": len(yt_links),
            "documents": [
                {
                    "id": str(r.id),
                    "file_name": r.file_name,
                    "file_size": r.size_bytes,
                    "has_transcript": bool(r.transcript_text),
                }
                for r in resources
            ],
            "videos": [
                {
                    "title": y.title or y.video_id,
                    "has_transcript": bool(y.transcript_text),
                }
                for y in yt_links
            ],
        }

    def _tool_get_topic_knowledge_state(self, topic_name: str) -> dict[str, Any]:
        """Retrieve student's mastery score and recorded misconceptions for a topic."""
        knowledge = get_topic_knowledge_state(self.student_id, self.subject_id, topic_name, self.db)
        if not knowledge:
            return {
                "topic_name": topic_name,
                "tracked": False,
                "mastery_score": 0,
                "confidence_score": 0,
                "misconceptions": [],
                "understood_concepts": [],
            }
        return {
            "topic_name": knowledge.topic_name,
            "tracked": True,
            "mastery_score": knowledge.mastery_score,
            "confidence_score": knowledge.confidence_score,
            "misconceptions": knowledge.misconceptions or [],
            "understood_concepts": knowledge.understood_concepts or [],
            "recommended_action": knowledge.recommended_action,
        }

    def _tool_record_evidence_based_knowledge(
        self,
        topic_name: str,
        evidence_type: str,
        understood_concept: str | None = None,
        misconception: str | None = None,
        delta_mastery: int = 0,
        notes: str = "",
    ) -> dict[str, Any]:
        """Record verified evidence of student understanding or confusion."""
        evidence = record_student_learning_evidence(
            student_id=self.student_id,
            subject_id=self.subject_id,
            topic_name=topic_name,
            evidence_type=evidence_type,
            db=self.db,
            understood_concept=understood_concept,
            misconception=misconception,
            delta_mastery=delta_mastery,
            notes=notes,
        )
        return {
            "status": "recorded",
            "topic": evidence.topic_name,
            "evidence_type": evidence.evidence_type,
            "delta_mastery": evidence.delta_mastery,
            "delta_confidence": evidence.delta_confidence,
        }

    def _tool_get_conversation_history(self, thread_id: str, limit: int = 6) -> dict[str, Any]:
        """Retrieve recent turns from the active thread for context continuity."""
        try:
            tid = UUID(thread_id)
        except (ValueError, TypeError):
            return {"messages": []}

        thread = self.db.get(ChatThread, tid)
        if not thread or thread.student_id != self.student_id or thread.subject_id != self.subject_id:
            return {"messages": []}

        msgs = self.db.scalars(
            select(ChatMessage)
            .where(ChatMessage.thread_id == tid)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        ).all()

        return {
            "messages": [
                {"role": m.role, "content": m.content[:1000]}
                for m in reversed(msgs)
            ]
        }

    def _tool_get_subject_academic_chapters(self) -> dict[str, Any]:
        """Fetch logically organized course chapters and any detected missing sequence gaps."""
        from app.services.knowledge_ingestion.academic_organizer import organize_subject_academic_hierarchy
        report = organize_subject_academic_hierarchy(self.db, self.subject_id)
        return {
            "total_chapters": report.total_chapters_detected,
            "chapters": report.ordered_chapters,
            "missing_chapters": report.detected_missing_chapters,
            "unclassified_resources": report.unclassified_resources,
        }

    def _tool_get_concept_with_prerequisites(self, query: str) -> dict[str, Any]:
        """Retrieve concepts matching the query and their prerequisite foundational concepts."""
        from app.services.retrieval import retrieve_concept_and_prerequisites
        return retrieve_concept_and_prerequisites(self.db, subject_id=self.subject_id, query=query)

    def _tool_get_cross_document_connections(self) -> dict[str, Any]:
        """Retrieve cross-document relationships and detected contradictions between course files."""
        from app.db.models import ConceptRelationship, ExtractedConcept
        from app.services.knowledge_ingestion.schemas import RelationshipType

        conflicts = self.db.scalars(
            select(ConceptRelationship).where(
                ConceptRelationship.subject_id == self.subject_id,
                ConceptRelationship.relationship_type == RelationshipType.POTENTIALLY_CONFLICTS_WITH.value,
            )
        ).all()

        return {
            "conflicts_count": len(conflicts),
            "conflicts": [
                {"description": c.description, "details": c.conflict_details}
                for c in conflicts
            ],
        }

    # ── Video Learning Tools ────────────────────────────────────────────────

    def _tool_analyze_video_url(self, url: str) -> dict[str, Any]:
        """Validate an educational video URL, extract metadata/captions, and process into knowledge."""
        from app.services.video_learning import parse_youtube_video_id, process_video_learning

        video_id = parse_youtube_video_id(url)
        link = self.db.scalar(
            select(YouTubeLink).where(
                YouTubeLink.subject_id == self.subject_id,
                YouTubeLink.video_id == video_id,
            )
        )
        if not link:
            link = YouTubeLink(
                id=uuid4(),
                subject_id=self.subject_id,
                owner_id=self.student_id,
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                processing_status="pending",
            )
            self.db.add(link)
            self.db.commit()
            self.db.refresh(link)

        res = process_video_learning(db=self.db, youtube_link_id=link.id)
        return {
            "video_id": res.video_id,
            "title": res.title,
            "status": res.status.value,
            "duration_seconds": res.duration_seconds,
            "has_captions": res.has_captions,
            "segments_count": res.segments_count,
            "concepts_count": res.concepts_count,
            "visual_analysis_status": res.visual_analysis_status,
            "markdown_storage_key": res.markdown_storage_key,
            "error": res.error,
        }

    def _tool_get_video_processing_status(self, video_id_or_url: str) -> dict[str, Any]:
        """Get the current processing lifecycle status and details of a video."""
        from app.services.video_learning import parse_youtube_video_id

        try:
            vid = parse_youtube_video_id(video_id_or_url)
        except Exception:
            vid = video_id_or_url.strip()

        link = self.db.scalar(
            select(YouTubeLink).where(
                YouTubeLink.subject_id == self.subject_id,
                (YouTubeLink.video_id == vid) | (YouTubeLink.id.cast(String) == vid),
            )
        )
        if not link:
            return {"found": False, "error": f"Video '{video_id_or_url}' not found in subject library."}

        chunks_count = self.db.scalar(
            select(func.count(YouTubeChunk.id)).where(YouTubeChunk.youtube_link_id == link.id)
        ) or 0

        return {
            "found": True,
            "video_id": link.video_id,
            "title": link.title,
            "channel_name": link.channel_name,
            "duration_seconds": link.duration_seconds,
            "status": link.processing_status,
            "has_transcript": bool(link.transcript_text),
            "transcript_language": link.transcript_language,
            "visual_analysis_status": link.visual_analysis_status,
            "visual_summary": link.visual_summary,
            "segments_indexed": chunks_count,
            "canonical_markdown_key": link.markdown_storage_key,
        }

    def _tool_retrieve_video_segments(
        self,
        video_id: str,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> dict[str, Any]:
        """Retrieve timestamped segments and visual observations for a video within an optional time range."""
        from app.services.video_learning import build_youtube_timestamp_url, format_timestamp

        link = self.db.scalar(
            select(YouTubeLink).where(
                YouTubeLink.subject_id == self.subject_id,
                YouTubeLink.video_id == video_id,
            )
        )
        if not link:
            return {"error": f"Video {video_id} not found", "segments": []}

        query = select(YouTubeChunk).where(YouTubeChunk.youtube_link_id == link.id)
        if start_time is not None:
            query = query.where(YouTubeChunk.end_seconds >= start_time)
        if end_time is not None:
            query = query.where(YouTubeChunk.start_seconds <= end_time)

        query = query.order_by(YouTubeChunk.chunk_index)
        chunks = self.db.scalars(query).all()

        return {
            "video_id": video_id,
            "title": link.title,
            "total_segments": len(chunks),
            "segments": [
                {
                    "chunk_index": c.chunk_index,
                    "title": c.segment_title,
                    "start_seconds": c.start_seconds,
                    "end_seconds": c.end_seconds,
                    "formatted_time": f"[{format_timestamp(c.start_seconds or 0)} - {format_timestamp(c.end_seconds or 0)}]",
                    "clickable_url": build_youtube_timestamp_url(video_id, c.start_seconds or 0),
                    "content": c.content,
                    "visual_description": c.visual_description,
                }
                for c in chunks
            ],
        }

    def _tool_search_video_knowledge(self, query: str, video_id: str | None = None) -> dict[str, Any]:
        """Search video lecture knowledge, transcripts, and visual observations for specific concepts."""
        from app.services.retrieval import retrieve_for_subject
        from app.services.video_learning import build_youtube_timestamp_url, format_timestamp

        passages = retrieve_for_subject(
            self.db,
            subject_id=self.subject_id,
            query=query,
            limit=6,
        )
        # Filter for YouTube passages
        yt_passages = [p for p in passages if "YouTube:" in p.file_name]

        return {
            "query": query,
            "matches_count": len(yt_passages),
            "matches": [
                {
                    "source_title": p.file_name,
                    "content": p.content,
                    "start_seconds": p.start_seconds,
                    "end_seconds": p.end_seconds,
                    "timestamp_url": p.timestamp_url,
                    "formatted_time": format_timestamp(p.start_seconds) if p.start_seconds is not None else None,
                    "visual_description": p.visual_description,
                }
                for p in yt_passages
            ],
        }

    def _tool_get_video_segment(self, video_id: str, timestamp_seconds: float) -> dict[str, Any]:
        """Retrieve the exact lesson segment and visual observations around a specific second timestamp."""
        from app.services.video_learning import build_youtube_timestamp_url, format_timestamp

        link = self.db.scalar(
            select(YouTubeLink).where(
                YouTubeLink.subject_id == self.subject_id,
                YouTubeLink.video_id == video_id,
            )
        )
        if not link:
            return {"error": f"Video {video_id} not found."}

        # Find closest chunk containing or nearest to timestamp_seconds
        chunk = self.db.scalar(
            select(YouTubeChunk)
            .where(
                YouTubeChunk.youtube_link_id == link.id,
                YouTubeChunk.start_seconds <= timestamp_seconds,
                YouTubeChunk.end_seconds >= timestamp_seconds,
            )
            .limit(1)
        )
        if not chunk:
            # Fallback to nearest chunk by chunk index or time
            chunk = self.db.scalar(
                select(YouTubeChunk)
                .where(YouTubeChunk.youtube_link_id == link.id)
                .order_by(func.abs(YouTubeChunk.start_seconds - timestamp_seconds))
                .limit(1)
            )

        if not chunk:
            return {"found": False, "message": "No indexed segments found for this video."}

        return {
            "found": True,
            "video_id": video_id,
            "video_title": link.title,
            "segment_title": chunk.segment_title,
            "start_seconds": chunk.start_seconds,
            "end_seconds": chunk.end_seconds,
            "formatted_time": f"[{format_timestamp(chunk.start_seconds or 0)} - {format_timestamp(chunk.end_seconds or 0)}]",
            "clickable_url": build_youtube_timestamp_url(video_id, chunk.start_seconds or 0),
            "instructor_explanation": chunk.content,
            "visual_observations": chunk.visual_description,
        }

    def _tool_compare_video_with_resources(
        self,
        video_id: str,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Compare the video instructor's explanation with uploaded textbooks and documents."""
        from app.services.retrieval import retrieve_for_subject

        link = self.db.scalar(
            select(YouTubeLink).where(
                YouTubeLink.subject_id == self.subject_id,
                YouTubeLink.video_id == video_id,
            )
        )
        if not link:
            return {"error": f"Video {video_id} not found"}

        search_query = query or link.title or "concepts"
        all_passages = retrieve_for_subject(self.db, subject_id=self.subject_id, query=search_query, limit=8)

        video_passages = [p for p in all_passages if str(p.resource_id) == str(link.id) or "YouTube:" in p.file_name]
        doc_passages = [p for p in all_passages if str(p.resource_id) != str(link.id) and "YouTube:" not in p.file_name]

        return {
            "video_title": link.title,
            "query": search_query,
            "video_passages_count": len(video_passages),
            "document_passages_count": len(doc_passages),
            "video_explanations": [
                {
                    "content": p.content,
                    "timestamp_url": p.timestamp_url,
                    "start_seconds": p.start_seconds,
                }
                for p in video_passages[:3]
            ],
            "document_explanations": [
                {
                    "file_name": p.file_name,
                    "page_number": p.page_number,
                    "content": p.content,
                }
                for p in doc_passages[:3]
            ],
            "comparison_guidance": "Compare the instructor's video remarks with the textbook passages: highlight agreements, practical tips from the video, and formal textbook definitions.",
        }


