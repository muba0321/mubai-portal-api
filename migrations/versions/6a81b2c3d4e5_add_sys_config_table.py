from alembic import op
import sqlalchemy as sa

revision = "6a81b2c3d4e5"
down_revision = "5f7084674727"
branch_labels = None
depends_on = None


def upgrade():
    # 创建 sys_config 表（Apollo 风格：namespace + key-value）
    op.create_table(
        "sys_config",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("namespace", sa.String(64), nullable=False),
        sa.Column("config_key", sa.String(128), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=True),
        sa.Column("config_type", sa.String(32), nullable=True, default="string"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("namespace", "config_key", name="uq_namespace_config_key"),
    )
    op.create_index("ix_sys_config_namespace", "sys_config", ["namespace"], unique=False)


def downgrade():
    op.drop_index("ix_sys_config_namespace", table_name="sys_config")
    op.drop_table("sys_config")
