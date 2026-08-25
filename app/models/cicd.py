"""
CICD 流程阶段管理模型
"""
from datetime import datetime
from app.extensions import db


class CICDStageConfig(db.Model):
    """CICD 阶段配置表"""
    __tablename__ = "cicd_stage_config"

    id = db.Column(db.Integer, primary_key=True)
    stage_name = db.Column(db.String(20), nullable=False, unique=True, comment="阶段名称")
    stage_order = db.Column(db.Integer, nullable=False, comment="阶段顺序")
    stage_icon = db.Column(db.String(50), comment="阶段图标")
    stage_color = db.Column(db.String(20), comment="阶段颜色")
    description = db.Column(db.Text, comment="阶段描述")
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 关联里程碑
    milestones = db.relationship("CICDMilestone", backref="stage", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.stage_name,
            "icon": self.stage_icon,
            "color": self.stage_color,
            "order": self.stage_order,
            "description": self.description,
        }


class CICDMilestone(db.Model):
    """CICD 里程碑表"""
    __tablename__ = "cicd_milestone"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    stage_name = db.Column(db.String(20), db.ForeignKey("cicd_stage_config.stage_name"), nullable=False, comment="所属阶段")
    title = db.Column(db.String(255), nullable=False, comment="里程碑标题")
    description = db.Column(db.Text, comment="里程碑描述")
    target_date = db.Column(db.Date, comment="目标日期")
    status = db.Column(db.String(20), default="pending", comment="状态：pending/in_progress/completed")
    completion_rate = db.Column(db.Integer, default=0, comment="完成率 0-100")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "stage_name": self.stage_name,
            "title": self.title,
            "description": self.description,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "status": self.status,
            "completion_rate": self.completion_rate,
        }
