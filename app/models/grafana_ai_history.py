from datetime import datetime
from app.extensions import db


class GrafanaAiHistory(db.Model):
    """Grafana AI 面板生成记录"""
    __tablename__ = "grafana_ai_history"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    dashboard_uid = db.Column(db.String(128), comment="目标仪表盘 UID")
    dashboard_title = db.Column(db.String(256), comment="仪表盘标题")
    operation = db.Column(db.String(16), comment="操作类型: add/modify/delete")
    description = db.Column(db.Text, comment="用户描述")
    panel_json = db.Column(db.JSON, comment="生成的面板 JSON")
    explanation = db.Column(db.Text, comment="AI 说明")
    status = db.Column(db.String(16), default="success", comment="状态: success/error")
    error_msg = db.Column(db.Text, comment="错误信息")
    user_id = db.Column(db.Integer, comment="操作用户 ID")
    username = db.Column(db.String(64), comment="操作用户名")
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<GrafanaAiHistory {self.id} {self.operation} {self.dashboard_uid}>"
