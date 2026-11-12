"""Add knowledge ingestion, academic organization, and concept graph tables.

Revision ID: 0018_knowledge_pipeline
Revises: 0017_student_learning_intel
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0018_knowledge_pipeline"
down_revision: str | None = "0017_student_learning_intel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    existing_tables = set(inspect(bind).get_table_names(schema=schema))
    existing_resource_cols = {col["name"] for col in inspect(bind).get_columns("resources", schema=schema)}

    # 1. Extend resources table
    new_cols = [
        ("markdown_storage_key", sa.String(512), True, None),
        ("markdown_storage_bucket", sa.String(128), True, None),
        ("academic_chapter", sa.Integer(), True, None),
        ("chapter_title", sa.String(255), True, None),
        ("document_version", sa.Integer(), False, "1"),
        ("ingestion_status", sa.String(32), False, "ready"),
        ("detected_gaps", sa.JSON(), False, "[]"),
    ]
    for col_name, col_type, nullable, server_def in new_cols:
        if col_name not in existing_resource_cols:
            kw = {"nullable": nullable}
            if server_def is not None:
                kw["server_default"] = sa.text(f"'{server_def}'") if isinstance(server_def, str) and not server_def.isdigit() else sa.text(str(server_def))
            op.add_column("resources", sa.Column(col_name, col_type, **kw), schema=schema)

    # 2. Academic Chapters Table
    if "academic_chapters" not in existing_tables:
        op.create_table(
            "academic_chapters",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("learning_objectives", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("subject_id", "chapter_number", name="uq_chapter_subject_number"),
            schema=schema,
        )
        op.create_index(
            "ix_academic_chapters_subject",
            "academic_chapters",
            ["subject_id", "order_index"],
            schema=schema,
        )

    # 3. Academic Topics Table
    if "academic_topics" not in existing_tables:
        op.create_table(
            "academic_topics",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("chapter_id", sa.Uuid(as_uuid=True), sa.ForeignKey("academic_chapters.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("normalized_title", sa.String(255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("is_foundational", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_academic_topics_subject",
            "academic_topics",
            ["subject_id"],
            schema=schema,
        )
        op.create_index(
            "ix_academic_topics_chapter",
            "academic_topics",
            ["chapter_id"],
            schema=schema,
        )

    # 4. Extracted Concepts Table
    if "extracted_concepts" not in existing_tables:
        op.create_table(
            "extracted_concepts",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("topic_id", sa.Uuid(as_uuid=True), sa.ForeignKey("academic_topics.id", ondelete="SET NULL"), nullable=True),
            sa.Column("resource_id", sa.Uuid(as_uuid=True), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("normalized_name", sa.String(200), nullable=False),
            sa.Column("definition", sa.Text(), nullable=False),
            sa.Column("concept_type", sa.String(64), nullable=False, server_default="concept"),
            sa.Column("page_or_slide_number", sa.Integer(), nullable=True),
            sa.Column("source_excerpt", sa.Text(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_extracted_concepts_subject",
            "extracted_concepts",
            ["subject_id"],
            schema=schema,
        )
        op.create_index(
            "ix_extracted_concepts_resource",
            "extracted_concepts",
            ["resource_id"],
            schema=schema,
        )
        op.create_index(
            "ix_extracted_concepts_name",
            "extracted_concepts",
            ["normalized_name"],
            schema=schema,
        )

    # 5. Concept Relationships Table
    if "concept_relationships" not in existing_tables:
        op.create_table(
            "concept_relationships",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_concept_id", sa.Uuid(as_uuid=True), sa.ForeignKey("extracted_concepts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_concept_id", sa.Uuid(as_uuid=True), sa.ForeignKey("extracted_concepts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("relationship_type", sa.String(64), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("conflict_details", sa.Text(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("source_concept_id", "target_concept_id", "relationship_type", name="uq_concept_rel_pair"),
            schema=schema,
        )
        op.create_index(
            "ix_concept_relationships_subject",
            "concept_relationships",
            ["subject_id"],
            schema=schema,
        )

    # 6. Knowledge Processing Jobs Table
    if "knowledge_processing_jobs" not in existing_tables:
        op.create_table(
            "knowledge_processing_jobs",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("resource_id", sa.Uuid(as_uuid=True), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
            sa.Column("current_stage", sa.String(64), nullable=False, server_default="queued"),
            sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("parser_version", sa.String(32), nullable=False, server_default="v2.0"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_knowledge_processing_jobs_resource",
            "knowledge_processing_jobs",
            ["resource_id"],
            schema=schema,
        )
        op.create_index(
            "ix_knowledge_processing_jobs_status",
            "knowledge_processing_jobs",
            ["status"],
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    existing_tables = set(inspect(bind).get_table_names(schema=schema))
    existing_resource_cols = {col["name"] for col in inspect(bind).get_columns("resources", schema=schema)}

    for t in [
        "knowledge_processing_jobs",
        "concept_relationships",
        "extracted_concepts",
        "academic_topics",
        "academic_chapters",
    ]:
        if t in existing_tables:
            op.drop_table(t, schema=schema)

    cols_to_drop = [
        "detected_gaps",
        "ingestion_status",
        "document_version",
        "chapter_title",
        "academic_chapter",
        "markdown_storage_bucket",
        "markdown_storage_key",
    ]
    for c in cols_to_drop:
        if c in existing_resource_cols:
            op.drop_column("resources", c, schema=schema)
