from datetime import datetime
from app.extensions import db


class Dept(db.Model):
    """部门（树形结构）"""
    __tablename__ = "sys_dept"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, comment="部门名称")
    parent_id = db.Column(db.Integer, default=0, comment="父部门ID, 0=根节点")
    ancestors = db.Column(db.String(500), comment="祖级列表, 如 0,1,3,5")
    leader = db.Column(db.String(64), comment="负责人姓名")
    phone = db.Column(db.String(20), comment="联系电话")
    email = db.Column(db.String(128), comment="邮箱")
    sort = db.Column(db.Integer, default=0, comment="排序")
    status = db.Column(db.Integer, default=1, comment="状态: 0=停用, 1=正常")
    deleted = db.Column(db.Integer, default=0, comment="逻辑删除")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Dept {self.name}>"
