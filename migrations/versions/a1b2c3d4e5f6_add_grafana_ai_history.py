from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "8b91c2d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "grafana_ai_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dashboard_uid", sa.String(128), comment="目标仪表盘 UID"),
        sa.Column("dashboard_title", sa.String(256), comment="仪表盘标题"),
        sa.Column("operation", sa.String(16), comment="操作类型: add/modify/delete"),
        sa.Column("description", sa.Text(), comment="用户描述"),
        sa.Column("panel_json", sa.JSON(), comment="生成的面板 JSON"),
        sa.Column("explanation", sa.Text(), comment="AI 说明"),
        sa.Column("status", sa.String(16), server_default="success", comment="状态: success/error"),
        sa.Column("error_msg", sa.Text(), comment="错误信息"),
        sa.Column("user_id", sa.Integer(), comment="操作用户 ID"),
        sa.Column("username", sa.String(64), comment="操作用户名"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_grafana_ai_history_uid", "grafana_ai_history", ["dashboard_uid"])
    op.create_index("idx_grafana_ai_history_user", "grafana_ai_history", ["user_id"])
    op.create_index("idx_grafana_ai_history_created", "grafana_ai_history", ["created_at"])


def downgrade():
    op.drop_index("idx_grafana_ai_history_created", table_name="grafana_ai_history")
    op.drop_index("idx_grafana_ai_history_user", table_name="grafana_ai_history")
    op.drop_index("idx_grafana_ai_history_uid", table_name="grafana_ai_history")
    op.drop_table("grafana_ai_history")
