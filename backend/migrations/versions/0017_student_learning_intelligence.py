"""Add student_learning_profiles and student_topic_knowledge tables.

Revision ID: 0017_student_learning_intelligence
Revises: 0016_neon_object_storage
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0017_student_learning_intel"
down_revision: str | None = "0016_neon_object_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    existing_tables = set(inspect(bind).get_table_names(schema=schema))

    if "student_learning_profiles" not in existing_tables:
        op.create_table(
            "student_learning_profiles",
            sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("learning_style", sa.String(32), nullable=False, server_default="balanced"),
            sa.Column("explanation_depth", sa.String(32), nullable=False, server_default="balanced"),
            sa.Column("preferred_language", sa.String(16), nullable=False, server_default="ar"),
            sa.Column("visual_preference", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("custom_instructions", sa.Text(), nullable=True),
            sa.Column("total_study_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sessions_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_student_learning_profiles_student_id",
            "student_learning_profiles",
            ["student_id"],
            schema=schema,
        )

    if "student_topic_knowledge" not in existing_tables:
        op.create_table(
            "student_topic_knowledge",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("topic_name", sa.String(200), nullable=False),
            sa.Column("mastery_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("understood_concepts", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("misconceptions", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("last_evidence_type", sa.String(64), nullable=True),
            sa.Column("recommended_action", sa.String(255), nullable=True),
            sa.Column("interaction_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("student_id", "subject_id", "topic_name", name="uq_student_subject_topic"),
            schema=schema,
        )
        op.create_index(
            "ix_student_topic_knowledge_student_subject",
            "student_topic_knowledge",
            ["student_id", "subject_id"],
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    existing_tables = set(inspect(bind).get_table_names(schema=schema))

    if "student_topic_knowledge" in existing_tables:
        op.drop_table("student_topic_knowledge", schema=schema)
    if "student_learning_profiles" in existing_tables:
        op.drop_table("student_learning_profiles", schema=schema)
