"""Add user activity tracking and multi-model AI task routing configs."""

from typing import Sequence
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0012_admin_ai_configs"
down_revision: str | None = "0011_study_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    schema = "public" if bind.dialect.name == "postgresql" else None

    # 1. Add last_active_at to profiles if missing
    profile_columns = [col["name"] for col in insp.get_columns("profiles", schema=schema)]
    if "last_active_at" not in profile_columns:
        op.add_column(
            "profiles",
            sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            schema=schema,
        )

    # 2. Create ai_model_configs table if missing
    if not insp.has_table("ai_model_configs", schema=schema):
        op.create_table(
            "ai_model_configs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("task_type", sa.String(length=64), nullable=False),
            sa.Column("model_name", sa.String(length=128), nullable=False),
            sa.Column("api_key", sa.String(length=512), nullable=True),
            sa.Column("temperature", sa.Float(), server_default="0.2", nullable=False),
            sa.Column("max_output_tokens", sa.Integer(), server_default="2000", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(
            "ix_ai_model_configs_task_type",
            "ai_model_configs",
            ["task_type"],
            unique=True,
            schema=schema,
        )

        # Seed initial cost-effective task routing
        configs_table = sa.table(
            "ai_model_configs",
            sa.column("id", sa.Uuid()),
            sa.column("task_type", sa.String()),
            sa.column("model_name", sa.String()),
            sa.column("temperature", sa.Float()),
            sa.column("max_output_tokens", sa.Integer()),
            sa.column("is_active", sa.Boolean()),
            sa.column("description", sa.String()),
        )
        op.bulk_insert(
            configs_table,
            [
                {
                    "id": uuid.uuid4(),
                    "task_type": "chat_qa",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.2,
                    "max_output_tokens": 900,
                    "is_active": True,
                    "description": "نموذج خفيف وسريع للإجابة المباشرة الموثقة بالمصادر بأقل توكنز",
                },
                {
                    "id": uuid.uuid4(),
                    "task_type": "quiz_generation",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.2,
                    "max_output_tokens": 1800,
                    "is_active": True,
                    "description": "نموذج اقتصادي فائق الدقة لإنشاء اختبارات MCQ وخيارات متعددة",
                },
                {
                    "id": uuid.uuid4(),
                    "task_type": "flashcards",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.2,
                    "max_output_tokens": 3000,
                    "is_active": True,
                    "description": "توليد بطاقات استذكار موجزة بأعلى كفاءة في استهلاك التوكنز",
                },
                {
                    "id": uuid.uuid4(),
                    "task_type": "concept_map",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.2,
                    "max_output_tokens": 3000,
                    "is_active": True,
                    "description": "استخراج شبكات العلاقات والمفاهيم الأساسية من المنهج",
                },
                {
                    "id": uuid.uuid4(),
                    "task_type": "study_notes",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.2,
                    "max_output_tokens": 7000,
                    "is_active": True,
                    "description": "تلخيص منظم وشامل للمذكرات الدراسية بسياق واسع",
                },
                {
                    "id": uuid.uuid4(),
                    "task_type": "audio_transcription",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.0,
                    "max_output_tokens": 10000,
                    "is_active": True,
                    "description": "تفريغ حرفي للمحاضرات الصوتية باللغة الأصلية بدون اختراع",
                },
                {
                    "id": uuid.uuid4(),
                    "task_type": "default",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.2,
                    "max_output_tokens": 2000,
                    "is_active": True,
                    "description": "الموديل الافتراضي الاحتياطي لتقليل التكلفة",
                },
            ],
        )


def downgrade() -> None:
    pass
