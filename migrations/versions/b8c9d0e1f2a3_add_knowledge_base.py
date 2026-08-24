"""add knowledge base tables

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "kb_files",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("file_path", sa.String(512), nullable=False, unique=True),
        sa.Column("file_name", sa.String(256), nullable=False),
        sa.Column("title", sa.String(256)),
        sa.Column("category", sa.String(64)),
        sa.Column("sub_category", sa.String(64)),
        sa.Column("file_size", sa.Integer),
        sa.Column("word_count", sa.Integer),
        sa.Column("content_text", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
        sa.Column("synced_at", sa.DateTime, server_default=sa.func.now()),
        sa.Index("idx_kb_category", "category"),
        sa.Index("idx_kb_title", "title"),
        sa.Index("idx_kb_path", "file_path"),
    )

    op.create_table(
        "kb_sync_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("files_added", sa.Integer, server_default="0"),
        sa.Column("files_updated", sa.Integer, server_default="0"),
        sa.Column("files_deleted", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("error_msg", sa.Text),
    )


def downgrade():
    op.drop_table("kb_sync_log")
    op.drop_table("kb_files")
