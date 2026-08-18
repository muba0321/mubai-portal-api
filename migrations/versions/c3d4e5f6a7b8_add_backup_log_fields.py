"""add file_name and file_md5 to service_backup_log

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-19 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('service_backup_log', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file_name', sa.String(255), comment="备份文件名"))
        batch_op.add_column(sa.Column('file_md5', sa.String(64), comment="文件 MD5 校验值"))


def downgrade():
    with op.batch_alter_table('service_backup_log', schema=None) as batch_op:
        batch_op.drop_column('file_md5')
        batch_op.drop_column('file_name')
