"""Add the API's missing objects while preserving the existing Neon schema.

Revision ID: 0008_api_compatibility
Revises: 0007_create_artifacts
Branch: neon_existing_schema
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.db.base import Base
from app.db import models  # noqa: F401

revision: str = "0008_api_compatibility"
down_revision: str | None = "0007_create_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CORE_TABLES = ("profiles", "subjects", "subject_members", "study_sessions")
API_TABLES = ("resources", "resource_chunks", "study_quizzes", "quiz_questions", "quiz_attempts")


def _add_missing_columns(table: str, columns: tuple[sa.Column, ...]) -> None:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table, schema="public" if op.get_bind().dialect.name == "postgresql" else None):
        return
    existing = {column["name"] for column in inspector.get_columns(table, schema="public" if op.get_bind().dialect.name == "postgresql" else None)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column, schema="public" if op.get_bind().dialect.name == "postgresql" else None)


def _checks(table: str) -> set[str]:
    schema = "public" if op.get_bind().dialect.name == "postgresql" else None
    return {item.get("name") for item in inspect(op.get_bind()).get_check_constraints(table, schema=schema)}


def _create_check_if_missing(table: str, name: str, condition: str) -> None:
    if name not in _checks(table):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table(table) as batch:
                batch.create_check_constraint(name, condition)
        else:
            op.create_check_constraint(name, table, condition, schema="public")


def _create_index_if_missing(table: str, name: str, columns: list[str]) -> None:
    schema = "public" if op.get_bind().dialect.name == "postgresql" else None
    indexes = {item["name"] for item in inspect(op.get_bind()).get_indexes(table, schema=schema)}
    if name not in indexes:
        op.create_index(name, table, columns, schema=schema)


def upgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    core = [Base.metadata.tables[name] for name in CORE_TABLES]
    # Fresh local databases get the same core tables as the existing Neon schema.
    Base.metadata.create_all(bind, tables=core, checkfirst=True)

    # Existing Neon tables lack only these nullable profile/content/session fields.
    _add_missing_columns("profiles", (sa.Column("email", sa.String(320), nullable=True),))
    _add_missing_columns("subjects", (sa.Column("description", sa.Text(), nullable=True),))
    _add_missing_columns("study_sessions", (sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),))

    _create_check_if_missing("profiles", "ck_user_profile_role", "role IN ('student', 'admin')")
    _create_check_if_missing("subjects", "ck_subject_name_nonempty", "length(trim(name)) > 0")
    _create_check_if_missing("study_sessions", "ck_study_session_positive_duration", "ends_at > started_at")
    _create_check_if_missing(
        "study_sessions", "ck_study_session_status", "status IN ('active', 'completed', 'cancelled')"
    )
    _create_index_if_missing("subject_members", "ix_subject_members_user_id", ["user_id"])

    # API-owned tables are additive. Legacy materials, stored_files, artifacts,
    # chunks, transcripts, audit and usage tables are deliberately untouched.
    api_tables = [Base.metadata.tables[name] for name in API_TABLES]
    Base.metadata.create_all(bind, tables=api_tables, checkfirst=True)


def downgrade() -> None:
    # Compatibility objects may contain user data once the API is in use.
    # Downgrade deliberately leaves the schema in place to avoid data loss.
    pass
