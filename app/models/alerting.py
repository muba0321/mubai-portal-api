from app.extensions import db
from datetime import datetime


class AlertMetric(db.Model):
    """告警指标定义"""
    __tablename__ = "alert_metrics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, comment="指标名称")
    display_name = db.Column(db.String(100), nullable=False, comment="展示名称")
    group = db.Column(db.String(50), nullable=False, comment="分组: system/mysql/jenkins/nginx/docker/custom")
    description = db.Column(db.String(500), comment="描述")
    promql = db.Column(db.Text, nullable=False, comment="PromQL 查询语句")
    unit = db.Column(db.String(20), comment="单位: %, ms, count 等")
    source_type = db.Column(db.String(20), default="builtin", comment="builtin/custom")
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AlertRule(db.Model):
    """告警规则"""
    __tablename__ = "alert_rules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, comment="规则名称")
    metric_id = db.Column(db.Integer, db.ForeignKey("alert_metrics.id"), comment="关联指标ID")
    condition_operator = db.Column(db.String(10), comment="比较符: >, <, >=, <=, ==")
    condition_value = db.Column(db.Float, comment="阈值")
    condition_duration = db.Column(db.Integer, default=60, comment="持续时间(秒)")
    severity = db.Column(db.String(10), default="P2", comment="P0/P1/P2")
    notification_channels = db.Column(db.String(500), comment="通知渠道ID列表,逗号分隔")
    source_type = db.Column(db.String(20), default="builtin", comment="builtin/custom")
    template_id = db.Column(db.Integer, db.ForeignKey("alert_templates.id"), comment="来源模板ID")
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    metric = db.relationship("AlertMetric", backref="rules")
    template = db.relationship("AlertTemplate", backref="rules")


class NotificationChannel(db.Model):
    """告警通知渠道"""
    __tablename__ = "notification_channels"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False, comment="dingtalk/wecom/email/webhook/slack")
    name = db.Column(db.String(100), nullable=False, comment="渠道名称")
    webhook_url = db.Column(db.Text, comment="Webhook URL")
    email_recipients = db.Column(db.String(500), comment="邮件接收人,逗号分隔")
    message_template = db.Column(db.Text, comment="消息模板")
    level_filter = db.Column(db.String(50), default="all", comment="级别过滤: all/P0/P1/P2,逗号分隔")
    silence_period = db.Column(db.Integer, default=300, comment="静默周期(秒)")
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AlertTemplate(db.Model):
    """告警模板（内置 + 用户自定义）"""
    __tablename__ = "alert_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment="模板名称")
    description = db.Column(db.String(500), comment="描述")
    group = db.Column(db.String(50), comment="分组: system/mysql/jenkins/nginx/docker/custom")
    source_type = db.Column(db.String(20), default="builtin", comment="builtin/custom")
    metric_count = db.Column(db.Integer, default=0, comment="指标数量")
    rule_count = db.Column(db.Integer, default=0, comment="规则数量")
    # JSON 存储模板包含的指标和规则定义
    metrics_def = db.Column(db.Text, comment="指标定义 JSON")
    rules_def = db.Column(db.Text, comment="规则定义 JSON")
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
