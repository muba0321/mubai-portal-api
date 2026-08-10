"""
密码管理 - 存储和管理各种服务的账号密码
"""
from datetime import datetime
from app.extensions import db


class Credential(db.Model):
    """账号密码凭证"""
    __tablename__ = "sys_credential"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment="服务/系统名称")
    category = db.Column(db.String(50), default="other", comment="分类: server/database/website/api/other")
    url = db.Column(db.String(500), comment="访问地址")
    username = db.Column(db.String(100), comment="用户名/账号")
    password = db.Column(db.String(500), comment="密码（加密存储）")
    remark = db.Column(db.Text, comment="备注")
    created_by = db.Column(db.String(64), comment="创建人")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Credential {self.name}>"
