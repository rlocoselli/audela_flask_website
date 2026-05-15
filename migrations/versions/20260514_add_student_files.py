"""add e_learning_student_files table

Revision ID: 20260514_add_student_files
Revises: 20260308_add_credit_approval_dates
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260514_add_student_files"
down_revision = "c06e8dd65b47"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "e_learning_student_files" in inspector.get_table_names():
        return

    op.create_table(
        "e_learning_student_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("module_id", sa.Integer, sa.ForeignKey("e_learning_modules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("lesson_id", sa.Integer, sa.ForeignKey("e_learning_lessons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_student_files_user", "e_learning_student_files", ["user_id"])
    op.create_index("ix_student_files_module", "e_learning_student_files", ["module_id"])
    op.create_index("ix_student_files_lesson", "e_learning_student_files", ["lesson_id"])


def downgrade():
    op.drop_table("e_learning_student_files")
