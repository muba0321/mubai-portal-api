"""
需求相关模型（扩展）
由 todo_extend 升级而来
"""
from datetime import datetime

from app.extensions import db


class RequirementAttachment(db.Model):
    """需求附件"""
    __tablename__ = "requirement_attachment"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False, comment="关联需求 ID")
    file_name = db.Column(db.String(255), nullable=False, comment="文件名")
    file_path = db.Column(db.String(500), nullable=False, comment="文件路径")
    file_size = db.Column(db.Integer, comment="文件大小 (bytes)")
    file_type = db.Column(db.String(50), comment="文件类型")
    uploaded_by = db.Column(db.String(64), comment="上传人")
    created_at = db.Column(db.DateTime, default=datetime.now)

    requirement = db.relationship("Requirement", backref="attachments")

    def __repr__(self):
        return f"<RequirementAttachment {self.file_name}>"


class RequirementComment(db.Model):
    """需求评论"""
    __tablename__ = "requirement_comment"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False, comment="关联需求 ID")
    content = db.Column(db.Text, nullable=False, comment="评论内容")
    created_by = db.Column(db.String(64), comment="创建人")
    created_at = db.Column(db.DateTime, default=datetime.now)

    requirement = db.relationship("Requirement", backref="comments")

    def __repr__(self):
        return f"<RequirementComment {self.id}>"


class RequirementLabel(db.Model):
    """需求标签（原 todo_tag）"""
    __tablename__ = "requirement_label"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, unique=True, comment="标签名称")
    color = db.Column(db.String(7), comment="标签颜色")
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<RequirementLabel {self.name}>"


class RequirementLabelMap(db.Model):
    """需求 - 标签关联"""
    __tablename__ = "requirement_label_map"

    requirement_id = db.Column(db.Integer, db.ForeignKey("requirement.id", ondelete="CASCADE"), primary_key=True)
    label_id = db.Column(db.Integer, db.ForeignKey("requirement_label.id", ondelete="CASCADE"), primary_key=True)


class RequirementVersion(db.Model):
    """需求版本历史"""
    __tablename__ = "requirement_version"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("requirement.id"))
    version_number = db.Column(db.Integer, nullable=False, comment="版本号")
    snapshot = db.Column(db.JSON(), comment="完整快照")
    changed_fields = db.Column(db.JSON(), comment="变更字段列表")
    changed_by = db.Column(db.Integer, db.ForeignKey("sys_user.id"), comment="变更人")
    change_type = db.Column(db.String(32), comment="变更类型")
    created_at = db.Column(db.DateTime, default=datetime.now)


class RequirementActivity(db.Model):
    """需求活动日志"""
    __tablename__ = "requirement_activity"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("requirement.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("sys_user.id"), comment="操作人")
    action = db.Column(db.String(64), nullable=False, comment="操作类型")
    field_name = db.Column(db.String(64), comment="变更字段")
    old_value = db.Column(db.Text, comment="旧值")
    new_value = db.Column(db.Text, comment="新值")
    created_at = db.Column(db.DateTime, default=datetime.now)


# ==================== 需求审批流模型 ====================
# 注意：避免与 approval.py 中的审批流模型冲突，使用 ReqApproval 前缀

class ReqApprovalTemplate(db.Model):
    """需求审批模板定义"""
    __tablename__ = "req_approval_template"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), comment="关联项目 NULL=全局")
    name = db.Column(db.String(128), nullable=False, comment="模板名称")
    description = db.Column(db.Text, comment="描述")
    trigger_conditions = db.Column(db.JSON(), comment="触发条件 JSON")
    is_active = db.Column(db.Boolean, default=True, comment="是否启用")
    created_at = db.Column(db.DateTime, default=datetime.now)

    nodes = db.relationship("ReqApprovalTemplateNode", backref="template", order_by="ReqApprovalTemplateNode.step_number")

    def __repr__(self):
        return f"<ReqApprovalTemplate {self.name}>"


class ReqApprovalTemplateNode(db.Model):
    """需求审批模板步骤"""
    __tablename__ = "req_approval_template_node"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    template_id = db.Column(db.BigInteger, db.ForeignKey("req_approval_template.id"))
    step_number = db.Column(db.Integer, nullable=False, comment="步骤序号")
    approver_type = db.Column(db.String(20), nullable=False, comment="审批人类型: user/role/group")
    approver_id = db.Column(db.String(128), comment="审批人 ID")
    approval_mode = db.Column(db.String(10), default="all", comment="审批模式: any/all")
    timeout_hours = db.Column(db.Integer, comment="超时小时数")
    escalate_to_id = db.Column(db.String(128), comment="升级目标")


class ReqApprovalInstance(db.Model):
    """需求审批运行时实例"""
    __tablename__ = "req_approval_instance"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("requirement.id"))
    template_id = db.Column(db.BigInteger, db.ForeignKey("req_approval_template.id"))
    status = db.Column(db.String(20), default="pending", comment="状态")
    current_step = db.Column(db.Integer, default=1, comment="当前步骤")
    initiated_by = db.Column(db.Integer, db.ForeignKey("sys_user.id"), comment="发起人")
    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime, comment="完成时间")

    records = db.relationship("ReqApprovalRecord", backref="instance", order_by="ReqApprovalRecord.created_at")

    def __repr__(self):
        return f"<ReqApprovalInstance {self.id} {self.status}>"


class ReqApprovalRecord(db.Model):
    """需求审批操作记录"""
    __tablename__ = "req_approval_record"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    instance_id = db.Column(db.BigInteger, db.ForeignKey("req_approval_instance.id"))
    step_number = db.Column(db.Integer, nullable=False, comment="步骤序号")
    approver_id = db.Column(db.Integer, db.ForeignKey("sys_user.id"), comment="审批人")
    action = db.Column(db.String(20), nullable=False, comment="操作: approved/rejected/delegated")
    comment = db.Column(db.Text, comment="审批意见")
    created_at = db.Column(db.DateTime, default=datetime.now)
