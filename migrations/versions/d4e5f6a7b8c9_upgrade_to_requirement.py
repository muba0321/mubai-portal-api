"""upgrade todo to requirement management module

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    # ==================== 重命名现有表 ====================
    op.rename_table("todo_item", "requirement")
    op.rename_table("todo_attachment", "requirement_attachment")
    op.rename_table("todo_comment", "requirement_comment")
    op.rename_table("todo_tag", "requirement_label")
    op.rename_table("todo_item_tag", "requirement_label_map")

    # ==================== 扩展 requirement 表 ====================
    with op.batch_alter_table("requirement", schema=None) as batch_op:
        # 新增字段
        batch_op.add_column(sa.Column("requirement_type", sa.String(20), server_default="task", comment="需求类型: feature/bug/task/improvement/tech_debt"))
        batch_op.add_column(sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("sys_user.id"), comment="提交人"))
        batch_op.add_column(sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("sys_user.id"), comment="负责人"))
        batch_op.add_column(sa.Column("milestone_id", sa.BigInteger(), comment="里程碑 ID"))
        batch_op.add_column(sa.Column("estimated_effort", sa.String(16), comment="预估工作量: XS/S/M/L/XL"))
        batch_op.add_column(sa.Column("tags", sa.JSON(), comment="标签缓存"))
        batch_op.add_column(sa.Column("version", sa.Integer(), server_default="1", comment="版本号"))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(), comment="审批通过时间"))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(), comment="完成时间"))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), comment="软删除时间"))
        # 修改 priority 字段长度
        batch_op.alter_column("priority", type_=sa.String(4))
        # 新增索引
        batch_op.create_index("idx_requirement_type", ["requirement_type"])
        batch_op.create_index("idx_requirement_reporter", ["reporter_id"])
        batch_op.create_index("idx_requirement_milestone", ["milestone_id"])
        batch_op.create_index("idx_requirement_deleted", ["deleted_at"])

    # ==================== 重命名外键（todo_item → requirement） ====================
    # 注意：外键重命名需要手动处理，这里通过修改约束名
    with op.batch_alter_table("requirement_attachment", schema=None) as batch_op:
        batch_op.alter_column("todo_id", new_column_name="requirement_id")

    with op.batch_alter_table("requirement_comment", schema=None) as batch_op:
        batch_op.alter_column("todo_id", new_column_name="requirement_id")

    with op.batch_alter_table("requirement_label_map", schema=None) as batch_op:
        batch_op.alter_column("todo_id", new_column_name="requirement_id")

    # ==================== 创建 milestone 表 ====================
    op.create_table(
        "milestone",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), comment="关联项目 ID"),
        sa.Column("title", sa.String(128), nullable=False, comment="里程碑标题"),
        sa.Column("description", sa.Text(), comment="描述"),
        sa.Column("due_date", sa.Date(), comment="截止日期"),
        sa.Column("status", sa.String(20), server_default="active", comment="状态: active/completed/archived"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_milestone_project", "milestone", ["project_id"])

    # ==================== 创建审批流表 ====================

    # approval_template
    op.create_table(
        "approval_template",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), comment="关联项目 NULL=全局"),
        sa.Column("name", sa.String(128), nullable=False, comment="模板名称"),
        sa.Column("description", sa.Text(), comment="描述"),
        sa.Column("trigger_conditions", sa.JSON(), comment="触发条件 JSON"),
        sa.Column("is_active", sa.Boolean(), server_default="1", comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # approval_template_node
    op.create_table(
        "approval_template_node",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("template_id", sa.BigInteger(), sa.ForeignKey("approval_template.id"), comment="关联模板"),
        sa.Column("step_number", sa.Integer(), nullable=False, comment="步骤序号"),
        sa.Column("approver_type", sa.String(20), nullable=False, comment="审批人类型: user/role/group"),
        sa.Column("approver_id", sa.String(128), comment="审批人 ID/角色名/组 ID"),
        sa.Column("approval_mode", sa.String(10), server_default="all", comment="审批模式: any/all"),
        sa.Column("timeout_hours", sa.Integer(), comment="超时小时数"),
        sa.Column("escalate_to_id", sa.String(128), comment="升级目标"),
    )
    op.create_index("idx_approval_node_template", "approval_template_node", ["template_id"])

    # approval_instance
    op.create_table(
        "approval_instance",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("requirement.id"), comment="关联需求"),
        sa.Column("template_id", sa.BigInteger(), sa.ForeignKey("approval_template.id"), comment="使用模板"),
        sa.Column("status", sa.String(20), server_default="pending", comment="状态: pending/in_progress/approved/rejected/canceled/escalated"),
        sa.Column("current_step", sa.Integer(), server_default="1", comment="当前步骤"),
        sa.Column("initiated_by", sa.Integer(), sa.ForeignKey("sys_user.id"), comment="发起人"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), comment="完成时间"),
    )
    op.create_index("idx_approval_instance_req", "approval_instance", ["requirement_id"])

    # approval_record
    op.create_table(
        "approval_record",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.BigInteger(), sa.ForeignKey("approval_instance.id"), comment="关联实例"),
        sa.Column("step_number", sa.Integer(), nullable=False, comment="步骤序号"),
        sa.Column("approver_id", sa.Integer(), sa.ForeignKey("sys_user.id"), comment="审批人"),
        sa.Column("action", sa.String(20), nullable=False, comment="操作: approved/rejected/delegated/skipped/escalated"),
        sa.Column("comment", sa.Text(), comment="审批意见"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_approval_record_instance", "approval_record", ["instance_id"])

    # ==================== 创建版本历史和活动日志表 ====================

    # requirement_version
    op.create_table(
        "requirement_version",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("requirement.id"), comment="关联需求"),
        sa.Column("version_number", sa.Integer(), nullable=False, comment="版本号"),
        sa.Column("snapshot", sa.JSON(), comment="完整快照"),
        sa.Column("changed_fields", sa.JSON(), comment="变更字段列表"),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("sys_user.id"), comment="变更人"),
        sa.Column("change_type", sa.String(32), comment="变更类型: create/update/status_change/approve/reject"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_req_version_req", "requirement_version", ["requirement_id"])

    # requirement_activity
    op.create_table(
        "requirement_activity",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("requirement.id"), comment="关联需求"),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("sys_user.id"), comment="操作人"),
        sa.Column("action", sa.String(64), nullable=False, comment="操作类型"),
        sa.Column("field_name", sa.String(64), comment="变更字段"),
        sa.Column("old_value", sa.Text(), comment="旧值"),
        sa.Column("new_value", sa.Text(), comment="新值"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_req_activity_req", "requirement_activity", ["requirement_id"])


def downgrade():
    # 删除新增表
    op.drop_table("requirement_activity")
    op.drop_table("requirement_version")
    op.drop_table("approval_record")
    op.drop_table("approval_instance")
    op.drop_table("approval_template_node")
    op.drop_table("approval_template")
    op.drop_table("milestone")

    # 恢复列名
    with op.batch_alter_table("requirement_attachment", schema=None) as batch_op:
        batch_op.alter_column("requirement_id", new_column_name="todo_id")
    with op.batch_alter_table("requirement_comment", schema=None) as batch_op:
        batch_op.alter_column("requirement_id", new_column_name="todo_id")
    with op.batch_alter_table("requirement_label_map", schema=None) as batch_op:
        batch_op.alter_column("requirement_id", new_column_name="todo_id")

    # 重命名回 todo_
    op.rename_table("requirement", "todo_item")
    op.rename_table("requirement_attachment", "todo_attachment")
    op.rename_table("requirement_comment", "todo_comment")
    op.rename_table("requirement_label", "todo_tag")
    op.rename_table("requirement_label_map", "todo_item_tag")
