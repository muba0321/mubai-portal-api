from datetime import datetime
from app.extensions import db


class Role(db.Model):
    """角色"""
    __tablename__ = "sys_role"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, comment="角色名称")
    code = db.Column(db.String(64), unique=True, nullable=False, comment="角色编码")
    sort = db.Column(db.Integer, default=0, comment="排序")
    data_scope = db.Column(db.String(32), default="self", comment="数据权限: all/dept/dept_and_child/self/custom")
    status = db.Column(db.Integer, default=1, comment="状态: 0=停用, 1=正常")
    remark = db.Column(db.String(500), comment="备注")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Role {self.name}>"
