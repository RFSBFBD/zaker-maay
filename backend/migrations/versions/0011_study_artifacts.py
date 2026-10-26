"""Add cached subject-scoped study artifacts."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0011_study_artifacts"
down_revision: str | None = "0010_audio_transcripts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = "public" if op.get_bind().dialect.name == "postgresql" else None
    if inspect(op.get_bind()).has_table("study_artifacts", schema=schema):
        return
    op.create_table(
        "study_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('flashcards', 'concept_map', 'study_notes')", name="ck_study_artifact_kind"),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "kind", "content_hash", name="uq_study_artifact_subject_kind_hash"),
        schema=schema,
    )
    op.create_index("ix_study_artifacts_subject_created", "study_artifacts", ["subject_id", "created_at"], schema=schema)


def downgrade() -> None:
    # Preserve user study artifacts during rollbacks; deletion requires an explicit data policy.
    pass
