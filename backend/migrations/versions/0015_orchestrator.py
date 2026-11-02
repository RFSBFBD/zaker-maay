"""Add fallback_model to AIModelConfig and orchestrator decisions table."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0015_orchestrator"
down_revision: str | None = "0014_youtube_transcripts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = "public" if op.get_bind().dialect.name == "postgresql" else None

    # Add fallback_model column to ai_model_configs
    if not _column_exists("ai_model_configs", "fallback_model", schema):
        op.add_column(
            "ai_model_configs",
            sa.Column("fallback_model", sa.String(128), nullable=True),
            schema=schema,
        )

    # Create orchestrator_decisions table
    op.create_table(
        "orchestrator_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("request_type", sa.String(32), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_orchestrator_decisions_created_at", "created_at"),
        sa.Index("ix_orchestrator_decisions_subject_id", "subject_id"),
        schema=schema,
    )


def downgrade() -> None:
    schema = "public" if op.get_bind().dialect.name == "postgresql" else None
    op.drop_table("orchestrator_decisions", schema=schema)
    op.drop_column("ai_model_configs", "fallback_model", schema=schema)


def _column_exists(table: str, column: str, schema: str | None) -> bool:
    bind = op.get_bind()
    inspector = bind.dialect.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table, schema=schema)]
    return column in columns
