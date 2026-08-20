"""add requirement_commits table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "requirement_commits",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("requirement_id", sa.Integer, sa.ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repo_module", sa.String(10), nullable=False, comment="仓库模块: 后端/前端"),
        sa.Column("commit_hash", sa.String(40), nullable=False, comment="提交 hash"),
        sa.Column("commit_subject", sa.String(256), comment="提交主题"),
        sa.Column("commit_date", sa.Date, comment="提交日期"),
        sa.Column("commit_author", sa.String(64), comment="提交作者"),
        sa.Column("files_changed", sa.JSON, comment="文件变更列表"),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
        sa.UniqueConstraint("requirement_id", "repo_module", "commit_hash", name="uk_req_commit"),
        sa.Index("idx_requirement", "requirement_id"),
        sa.Index("idx_commit", "commit_hash"),
    )


def downgrade():
    op.drop_table("requirement_commits")
