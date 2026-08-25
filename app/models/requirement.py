"""
需求管理模型
由 todo 模块升级而来
"""
from datetime import datetime

from app.extensions import db


class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active")
    sort = db.Column(db.Integer, default=0, comment="排序值，越小越靠前")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    requirements = db.relationship(
        "Requirement", backref="project", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    milestones = db.relationship("Milestone", backref="project", lazy="dynamic")

    def __repr__(self):
        return f"<Project {self.name}>"


class Requirement(db.Model):
    """需求（原 TodoItem）"""
    __tablename__ = "requirement"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("requirement.id", ondelete="CASCADE"), nullable=True)

    # 基本信息
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # 需求属性
    requirement_type = db.Column(db.String(20), default="task", comment="需求类型: feature/bug/task/improvement/tech_debt")
    priority = db.Column(db.String(4), default="P2", comment="优先级: P0/P1/P2/P3")
    status = db.Column(db.String(32), default="proposed", comment="状态")

    # 人员
    reporter_id = db.Column(db.Integer, db.ForeignKey("sys_user.id"), comment="提交人")
    assignee = db.Column(db.String(64), nullable=True, comment="负责人（兼容旧字段）")
    assignee_id = db.Column(db.Integer, db.ForeignKey("sys_user.id"), comment="负责人 ID")

    # 计划
    milestone_id = db.Column(db.BigInteger(), db.ForeignKey("milestone.id"), comment="里程碑 ID")
    due_date = db.Column(db.DateTime, nullable=True, comment="截止日期")
    estimated_effort = db.Column(db.String(16), comment="预估工作量: XS/S/M/L/XL")
    estimated_hours = db.Column(db.Numeric(5, 2), comment="预估工时（兼容旧字段）")
    actual_hours = db.Column(db.Numeric(5, 2), comment="实际工时")

    # 排序和版本
    view_order = db.Column(db.Integer, default=0, comment="看板排序")
    tags = db.Column(db.JSON(), comment="标签缓存")
    version = db.Column(db.Integer, default=1, comment="版本号")

    # CICD 阶段
    cicd_stage = db.Column(db.String(20), comment="CICD 阶段")

    # 时间戳
    approved_at = db.Column(db.DateTime, comment="审批通过时间")
    completed_at = db.Column(db.DateTime, comment="完成时间")
    deleted_at = db.Column(db.DateTime, comment="软删除时间")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 关系
    children = db.relationship(
        "Requirement",
        backref=db.backref("parent", remote_side=[id]),
        lazy="select",
    )
    approval_instance = db.relationship("ReqApprovalInstance", backref="requirement", uselist=False)

    def __repr__(self):
        return f"<Requirement {self.title}>"


class Milestone(db.Model):
    """里程碑"""
    __tablename__ = "milestone"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"))
    title = db.Column(db.String(128), nullable=False, comment="里程碑标题")
    description = db.Column(db.Text, comment="描述")
    due_date = db.Column(db.Date, comment="截止日期")
    status = db.Column(db.String(20), default="active", comment="状态: active/completed/archived")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    requirements = db.relationship("Requirement", backref="milestone_obj", lazy="dynamic")

    def __repr__(self):
        return f"<Milestone {self.title}>"


class RequirementCommit(db.Model):
    """需求与 Git 提交的多对多关联表"""
    __tablename__ = "requirement_commits"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False)
    repo_module = db.Column(db.String(10), nullable=False, comment="仓库模块: 后端/前端")
    commit_hash = db.Column(db.String(40), nullable=False, comment="提交 hash")
    commit_subject = db.Column(db.String(256), comment="提交主题")
    commit_date = db.Column(db.Date, comment="提交日期")
    commit_author = db.Column(db.String(64), comment="提交作者")
    files_changed = db.Column(db.JSON, comment="文件变更列表")
    created_at = db.Column(db.DateTime, default=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("requirement_id", "repo_module", "commit_hash", name="uk_req_commit"),
        db.Index("idx_requirement", "requirement_id"),
        db.Index("idx_commit", "commit_hash"),
    )

    requirement = db.relationship("Requirement", backref=db.backref("commits", lazy="dynamic"))

    def __repr__(self):
        return f"<RequirementCommit req={self.requirement_id} hash={self.commit_hash[:7]}>"
