"""add e_learning quiz tables

Revision ID: 20260514_add_quiz_tables
Revises: 20260514_add_student_files
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260514_add_quiz_tables"
down_revision = "20260514_add_student_files"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = inspector.get_table_names()

    if "e_learning_quizzes" not in existing:
        op.create_table(
            "e_learning_quizzes",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("lesson_id", sa.Integer, sa.ForeignKey("e_learning_lessons.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("code", sa.String(64), nullable=False, index=True),
            sa.Column("order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("title_i18n", sa.JSON, nullable=False),
            sa.Column("description_i18n", sa.JSON, nullable=True),
            sa.Column("time_limit_minutes", sa.Integer, nullable=True),
            sa.Column("pass_threshold", sa.Integer, nullable=False, server_default="70"),
            sa.Column("max_attempts", sa.Integer, nullable=True),
            sa.Column("shuffle_questions", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("show_correct_answers", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("points_on_pass", sa.Integer, nullable=False, server_default="20"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("lesson_id", "code", name="uq_quiz_code_per_lesson"),
        )

    if "e_learning_quiz_questions" not in existing:
        op.create_table(
            "e_learning_quiz_questions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("quiz_id", sa.Integer, sa.ForeignKey("e_learning_quizzes.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("question_type", sa.String(32), nullable=False, server_default="multiple_choice"),
            sa.Column("text_i18n", sa.JSON, nullable=False),
            sa.Column("explanation_i18n", sa.JSON, nullable=True),
            sa.Column("points", sa.Integer, nullable=False, server_default="1"),
            sa.Column("expected_answer", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        )

    if "e_learning_quiz_options" not in existing:
        op.create_table(
            "e_learning_quiz_options",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("question_id", sa.Integer, sa.ForeignKey("e_learning_quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("text_i18n", sa.JSON, nullable=False),
            sa.Column("is_correct", sa.Boolean, nullable=False, server_default="0"),
        )

    if "user_quiz_attempts" not in existing:
        op.create_table(
            "user_quiz_attempts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("quiz_id", sa.Integer, sa.ForeignKey("e_learning_quizzes.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("started_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("submitted_at", sa.DateTime, nullable=True),
            sa.Column("score_pct", sa.Integer, nullable=True),
            sa.Column("points_earned", sa.Integer, nullable=False, server_default="0"),
            sa.Column("passed", sa.Boolean, nullable=True),
            sa.Column("answers_json", sa.JSON, nullable=True),
        )


def downgrade():
    op.drop_table("user_quiz_attempts")
    op.drop_table("e_learning_quiz_options")
    op.drop_table("e_learning_quiz_questions")
    op.drop_table("e_learning_quizzes")
