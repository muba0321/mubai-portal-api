"""add service backup tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-18 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # 服务备份配置表
    op.create_table(
        "service_backup",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, comment="服务名称"),
        sa.Column("category", sa.String(30), comment="分类: database/monitoring/cicd/config/gateway/application/documentation"),
        sa.Column("description", sa.Text(), comment="功能描述"),
        sa.Column("server_ip", sa.String(20), comment="所属服务器 IP"),
        sa.Column("server_name", sa.String(100), comment="所属服务器名称"),
        sa.Column("port", sa.Integer(), comment="服务端口"),
        sa.Column("backup_method", sa.String(50), comment="备份方式"),
        sa.Column("backup_path", sa.String(500), comment="备份文件存储路径"),
        sa.Column("backup_script", sa.Text(), comment="备份脚本/命令"),
        sa.Column("restore_steps", sa.Text(), comment="恢复步骤（JSON 数组）"),
        sa.Column("enabled", sa.Boolean(), server_default="1", comment="是否启用备份"),
        sa.Column("sort", sa.Integer(), server_default="0", comment="排序"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_service_backup_category", "service_backup", ["category"])
    op.create_index("idx_service_backup_server", "service_backup", ["server_ip"])

    # 服务备份执行日志表
    op.create_table(
        "service_backup_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("service_backup.id"), comment="关联服务 ID"),
        sa.Column("status", sa.String(20), comment="success/failed/skipped"),
        sa.Column("file_path", sa.String(500), comment="备份文件路径"),
        sa.Column("file_size", sa.BigInteger(), comment="文件大小(bytes)"),
        sa.Column("error_msg", sa.Text(), comment="错误信息"),
        sa.Column("duration", sa.Integer(), comment="执行耗时(秒)"),
        sa.Column("started_at", sa.DateTime(), comment="开始时间"),
    )
    op.create_index("idx_service_backup_log_service", "service_backup_log", ["service_id"])
    op.create_index("idx_service_backup_log_started", "service_backup_log", ["started_at"])


def downgrade():
    op.drop_index("idx_service_backup_log_started", table_name="service_backup_log")
    op.drop_index("idx_service_backup_log_service", table_name="service_backup_log")
    op.drop_table("service_backup_log")
    op.drop_index("idx_service_backup_server", table_name="service_backup")
    op.drop_index("idx_service_backup_category", table_name="service_backup")
    op.drop_table("service_backup")
