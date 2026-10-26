"""add study quizzes and saved attempts

Revision ID: 18a7e42bc901
Revises: 6c419721a122
Create Date: 2026-10-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "18a7e42bc901"
down_revision: Union[str, None] = "6c419721a122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "study_quizzes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_quizzes_subject_created", "study_quizzes", ["subject_id", "created_at"], unique=False)
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("correct_answer", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source_resource_id", sa.Uuid(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.CheckConstraint("position >= 0", name="ck_quiz_question_position_nonnegative"),
        sa.CheckConstraint("correct_answer BETWEEN 0 AND 3", name="ck_quiz_question_answer_range"),
        sa.ForeignKeyConstraint(["quiz_id"], ["study_quizzes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_resource_id"], ["resources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_id", "position", name="uq_quiz_question_position"),
    )
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"], unique=False)
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= total_questions", name="ck_quiz_attempt_score_range"),
        sa.CheckConstraint("total_questions > 0", name="ck_quiz_attempt_total_positive"),
        sa.ForeignKeyConstraint(["quiz_id"], ["study_quizzes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_attempts_user_submitted", "quiz_attempts", ["user_id", "submitted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_user_submitted", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
    op.drop_index("ix_quiz_questions_quiz_id", table_name="quiz_questions")
    op.drop_table("quiz_questions")
    op.drop_index("ix_study_quizzes_subject_created", table_name="study_quizzes")
    op.drop_table("study_quizzes")
