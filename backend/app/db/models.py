from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserProfile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("role IN ('student', 'admin')", name="ck_user_profile_role"),
        Index("ix_profiles_auth_user_id", "auth_user_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    auth_user_id: Mapped[str] = mapped_column(String(255), nullable=False, default=lambda: str(uuid4()))
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student", server_default="student")
    skill_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, server_default=func.now())


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_subject_name_nonempty"),
        Index(
            "uq_subjects_owner_normalized_active",
            "created_by",
            "normalized_name",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
            sqlite_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        String(120), nullable=False,
        default=lambda context: str(context.get_current_parameters().get("name", "")).strip().casefold(),
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubjectMembership(Base):
    __tablename__ = "subject_members"
    __table_args__ = (Index("ix_subject_members_user_id", "user_id"),)

    subject_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student", server_default="student")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    @property
    def created_at(self) -> datetime:
        return self.joined_at


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        CheckConstraint("ends_at > started_at", name="ck_study_session_positive_duration"),
        CheckConstraint("status IN ('active', 'completed', 'cancelled')", name="ck_study_session_status"),
        Index("ix_study_sessions_user_id", "user_id"),
        Index("ix_study_sessions_status", "status"),
        Index("ix_study_sessions_subject_id", "subject_id"),
        Index("ix_study_sessions_ends_at", "ends_at"),
        Index(
            "uq_study_sessions_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"))
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    planned_end_at: Mapped[datetime] = mapped_column("ends_at", DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_resource_positive_size"),
        CheckConstraint(
            "processing_status IN ('pending', 'ready', 'no_text', 'unsupported', 'truncated', 'failed')",
            name="ck_resource_processing_status",
        ),
        UniqueConstraint("subject_id", "sha256", name="uq_resource_subject_sha256"),
        Index("ix_resources_subject_created", "subject_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"))
    uploaded_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    cloudinary_public_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    secure_url: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    transcript_language: Mapped[str | None] = mapped_column(String(35))
    transcription_model: Mapped[str | None] = mapped_column(String(100))
    audio_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    processing_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResourceChunk(Base):
    __tablename__ = "resource_chunks"
    __table_args__ = (
        CheckConstraint("length(trim(content)) > 0", name="ck_resource_chunk_content_nonempty"),
        UniqueConstraint("resource_id", "chunk_index", name="uq_resource_chunk_index"),
        Index("ix_resource_chunks_resource_id", "resource_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    resource_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class YouTubeLink(Base):
    __tablename__ = "youtube_links"
    __table_args__ = (
        CheckConstraint("length(video_id) = 11", name="ck_youtube_link_video_id_length"),
        UniqueConstraint("subject_id", "video_id", name="uq_youtube_link_subject_video"),
        Index("ix_youtube_links_subject_created", "subject_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"))
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"))
    video_id: Mapped[str] = mapped_column(String(11), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StudyQuiz(Base):
    __tablename__ = "study_quizzes"
    __table_args__ = (Index("ix_study_quizzes_subject_created", "subject_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"))
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_quiz_question_position_nonnegative"),
        CheckConstraint("correct_answer BETWEEN 0 AND 3", name="ck_quiz_question_answer_range"),
        UniqueConstraint("quiz_id", "position", name="uq_quiz_question_position"),
        Index("ix_quiz_questions_quiz_id", "quiz_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    quiz_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("study_quizzes.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    correct_answer: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source_resource_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resources.id", ondelete="SET NULL")
    )
    source_page: Mapped[int | None] = mapped_column(Integer)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= total_questions", name="ck_quiz_attempt_score_range"),
        CheckConstraint("total_questions > 0", name="ck_quiz_attempt_total_positive"),
        Index("ix_quiz_attempts_user_submitted", "user_id", "submitted_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    quiz_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("study_quizzes.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"))
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    answers: Mapped[list[dict[str, str | int]]] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StudyArtifact(Base):
    __tablename__ = "study_artifacts"
    __table_args__ = (
        CheckConstraint("kind IN ('flashcards', 'concept_map', 'study_notes')", name="ck_study_artifact_kind"),
        UniqueConstraint("subject_id", "kind", "content_hash", name="uq_study_artifact_subject_kind_hash"),
        Index("ix_study_artifacts_subject_created", "subject_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"))
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    sources: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"
    __table_args__ = (
        Index("ix_ai_model_configs_task_type", "task_type", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    temperature: Mapped[float] = mapped_column(nullable=False, default=0.2, server_default="0.2")
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=2000, server_default="2000")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StudentInquiry(Base):
    __tablename__ = "student_inquiries"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_student_inquiry_status"),
        Index("ix_student_inquiries_student", "student_id", "created_at"),
        Index("ix_student_inquiries_subject", "subject_id", "created_at"),
        Index("ix_student_inquiries_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    ai_suggested_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    admin_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatThread(Base):
    __tablename__ = "chat_threads"
    __table_args__ = (
        Index("ix_chat_threads_student_subject", "student_id", "subject_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="محادثة جديدة", server_default="محادثة جديدة")
    is_pinned: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
        Index("ix_chat_messages_thread", "thread_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    thread_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    media_svg: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    no_resources: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    out_of_scope: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = (
        Index("ix_agent_skills_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_github_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    system_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    skill_type: Mapped[str] = mapped_column(String(64), nullable=False, default="pedagogy", server_default="pedagogy")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
