"""Add batch uploads table and batch tracking columns.

Revision ID: 0019_batch_uploads
Revises: 0018_knowledge_pipeline
"""

from typing import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0019_batch_uploads"
down_revision: str | None = "0018_knowledge_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    existing_tables = set(inspect(bind).get_table_names(schema=schema))

    # 1. Create upload_batches table if not present
    if "upload_batches" not in existing_tables:
        op.create_table(
            "upload_batches",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "subject_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("subjects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "student_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("profiles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("title", sa.String(255), nullable=False, server_default="Untitled Batch"),
            sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("batch_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_upload_batches_subject_id", "upload_batches", ["subject_id"])
        op.create_index("ix_upload_batches_student_id", "upload_batches", ["student_id"])
        op.create_index("ix_upload_batches_status", "upload_batches", ["status"])

    # 2. Add batch_id to resources if missing
    existing_resource_cols = {col["name"] for col in inspect(bind).get_columns("resources", schema=schema)}
    if "batch_id" not in existing_resource_cols:
        op.add_column(
            "resources",
            sa.Column(
                "batch_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("upload_batches.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_resources_batch_id", "resources", ["batch_id"])

    # 3. Add batch_id to knowledge_processing_jobs if missing
    existing_job_cols = {col["name"] for col in inspect(bind).get_columns("knowledge_processing_jobs", schema=schema)}
    if "batch_id" not in existing_job_cols:
        op.add_column(
            "knowledge_processing_jobs",
            sa.Column(
                "batch_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("upload_batches.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_knowledge_processing_jobs_batch", "knowledge_processing_jobs", ["batch_id"])


def downgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    existing_tables = set(inspect(bind).get_table_names(schema=schema))

    existing_job_cols = {col["name"] for col in inspect(bind).get_columns("knowledge_processing_jobs", schema=schema)}
    if "batch_id" in existing_job_cols:
        op.drop_index("ix_knowledge_processing_jobs_batch", table_name="knowledge_processing_jobs")
        op.drop_column("knowledge_processing_jobs", "batch_id")

    existing_resource_cols = {col["name"] for col in inspect(bind).get_columns("resources", schema=schema)}
    if "batch_id" in existing_resource_cols:
        op.drop_index("ix_resources_batch_id", table_name="resources")
        op.drop_column("resources", "batch_id")

    if "upload_batches" in existing_tables:
        op.drop_index("ix_upload_batches_status", table_name="upload_batches")
        op.drop_index("ix_upload_batches_student_id", table_name="upload_batches")
        op.drop_index("ix_upload_batches_subject_id", table_name="upload_batches")
        op.drop_table("upload_batches")
