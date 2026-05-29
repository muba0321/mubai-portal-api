"""add category to sys_common_link"""

from alembic import op
import sqlalchemy as sa

revision = "8b91c2d5e6f7"
down_revision = "6a81b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sys_common_link", sa.Column("category", sa.String(50), nullable=True, comment="链接分类"))


def downgrade():
    op.drop_column("sys_common_link", "category")
