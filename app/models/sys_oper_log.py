from datetime import datetime
from app.extensions import db


class OperLog(db.Model):
    """操作日志"""
    __tablename__ = "sys_oper_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, comment="操作用户ID")
    username = db.Column(db.String(64), comment="操作用户名")
    module = db.Column(db.String(64), comment="操作模块")
    action = db.Column(db.String(64), comment="操作类型: create/update/delete/login")
    method = db.Column(db.String(256), comment="请求方法")
    request_method = db.Column(db.String(10), comment="请求方式: GET/POST/PUT/DELETE")
    ip = db.Column(db.String(128), comment="操作IP")
    status = db.Column(db.Integer, comment="状态: 0=失败, 1=成功")
    error_msg = db.Column(db.Text, comment="错误信息")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<OperLog {self.username} {self.action}>"
