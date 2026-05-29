import json
from datetime import datetime
from app.extensions import db


class ApprovalTemplate(db.Model):
    """审批模板"""
    __tablename__ = "approval_template"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, comment="模板名称")
    code = db.Column(db.String(64), unique=True, nullable=False, comment="模板编码")
    type = db.Column(db.String(32), nullable=False, comment="类型: role_change/dept_change/resource_access")
    description = db.Column(db.String(500), comment="描述")
    approvers = db.Column(db.Text, comment="审批人配置 JSON")
    enabled = db.Column(db.Integer, default=1, comment="是否启用")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_approvers(self):
        return json.loads(self.approvers) if self.approvers else []


class ApprovalRecord(db.Model):
    """审批记录"""
    __tablename__ = "approval_record"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("approval_template.id"), nullable=False, comment="审批模板ID")
    applicant_id = db.Column(db.Integer, db.ForeignKey("sys_user.id"), nullable=False, comment="申请人ID")
    title = db.Column(db.String(256), nullable=False, comment="审批标题")
    content = db.Column(db.Text, comment="审批内容 JSON")
    status = db.Column(db.String(32), default="pending", comment="状态: pending/approved/rejected/cancelled")
    current_level = db.Column(db.Integer, default=1, comment="当前审批级别")
    result = db.Column(db.Text, comment="审批结果备注")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    template = db.relationship("ApprovalTemplate", backref="records")
    applicant = db.relationship("SysUser", backref="approvals")
    steps = db.relationship("ApprovalStep", backref="approval", order_by="ApprovalStep.level")

    def get_content(self):
        return json.loads(self.content) if self.content else {}


class ApprovalStep(db.Model):
    """审批步骤"""
    __tablename__ = "approval_step"

    id = db.Column(db.Integer, primary_key=True)
    approval_id = db.Column(db.Integer, db.ForeignKey("approval_record.id"), nullable=False, comment="审批记录ID")
    level = db.Column(db.Integer, nullable=False, comment="审批级别")
    approver_id = db.Column(db.Integer, db.ForeignKey("sys_user.id"), nullable=False, comment="审批人ID")
    status = db.Column(db.String(32), default="pending", comment="pending/approved/rejected")
    comment = db.Column(db.Text, comment="审批意见")
    decided_at = db.Column(db.DateTime, comment="审批时间")

    # Relationship
    approver = db.relationship("SysUser", backref="approval_steps")

    def __repr__(self):
        return f"<ApprovalStep level={self.level} status={self.status}>"
