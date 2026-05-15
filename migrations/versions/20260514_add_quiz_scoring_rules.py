"""add quiz scoring rule columns

Revision ID: 20260514_add_quiz_scoring_rules
Revises: 20260514_add_quiz_tables
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260514_add_quiz_scoring_rules"
down_revision = "20260514_add_quiz_tables"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    cols = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in cols


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "e_learning_quiz_questions" in tables:
        if not _has_column(inspector, "e_learning_quiz_questions", "allow_partial_credit"):
            op.add_column(
                "e_learning_quiz_questions",
                sa.Column("allow_partial_credit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            )
        if not _has_column(inspector, "e_learning_quiz_questions", "penalty_points"):
            op.add_column(
                "e_learning_quiz_questions",
                sa.Column("penalty_points", sa.Integer(), nullable=False, server_default="0"),
            )

    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "user_quiz_attempts" in tables and not _has_column(inspector, "user_quiz_attempts", "question_scores_json"):
        op.add_column(
            "user_quiz_attempts",
            sa.Column("question_scores_json", sa.JSON(), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "user_quiz_attempts" in tables and _has_column(inspector, "user_quiz_attempts", "question_scores_json"):
        op.drop_column("user_quiz_attempts", "question_scores_json")

    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "e_learning_quiz_questions" in tables and _has_column(inspector, "e_learning_quiz_questions", "penalty_points"):
        op.drop_column("e_learning_quiz_questions", "penalty_points")

    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "e_learning_quiz_questions" in tables and _has_column(inspector, "e_learning_quiz_questions", "allow_partial_credit"):
        op.drop_column("e_learning_quiz_questions", "allow_partial_credit")
