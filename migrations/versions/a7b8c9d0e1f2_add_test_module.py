"""add test module tables

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    # 测试用例表
    op.create_table(
        "test_case",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("test_type", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("priority", sa.String(4), server_default="P2"),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("tags", sa.JSON),
        # API 测试配置
        sa.Column("api_method", sa.String(10)),
        sa.Column("api_url", sa.String(512)),
        sa.Column("api_headers", sa.JSON),
        sa.Column("api_body", sa.Text),
        sa.Column("api_expected_status", sa.Integer),
        sa.Column("api_expected_body", sa.Text),
        # 手工测试配置
        sa.Column("manual_steps", sa.JSON),
        sa.Column("preconditions", sa.Text),
        # 通用字段
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 测试用例与需求关联表
    op.create_table(
        "test_case_requirement",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("test_case_id", sa.Integer, sa.ForeignKey("test_case.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", sa.Integer, sa.ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 测试执行记录表
    op.create_table(
        "test_execution",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("test_case_id", sa.Integer, sa.ForeignKey("test_case.id", ondelete="CASCADE"), nullable=False),
        sa.Column("executor", sa.String(64)),
        sa.Column("result", sa.String(20)),
        sa.Column("actual_response", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("environment", sa.String(64)),
        sa.Column("executed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("duration_ms", sa.Integer),
    )

    # 测试执行步骤结果表
    op.create_table(
        "test_execution_step",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("execution_id", sa.Integer, sa.ForeignKey("test_execution.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20)),
        sa.Column("actual_result", sa.Text),
        sa.Column("notes", sa.Text),
    )


def downgrade():
    op.drop_table("test_execution_step")
    op.drop_table("test_execution")
    op.drop_table("test_case_requirement")
    op.drop_table("test_case")
