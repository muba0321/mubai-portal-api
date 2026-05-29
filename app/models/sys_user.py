from datetime import datetime
from app.extensions import db


class SysUser(db.Model):
    """用户（增强版）"""
    __tablename__ = "sys_user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, comment="用户名")
    password_hash = db.Column(db.String(256), nullable=False, comment="密码哈希")
    nickname = db.Column(db.String(64), comment="昵称")
    email = db.Column(db.String(128), comment="邮箱")
    phone = db.Column(db.String(20), comment="手机号")
    gender = db.Column(db.Integer, default=0, comment="性别: 0=未知, 1=男, 2=女")
    avatar = db.Column(db.String(256), comment="头像URL")
    dept_id = db.Column(db.Integer, db.ForeignKey("sys_dept.id"), comment="所属部门ID")
    identity = db.Column(db.String(32), default="member", comment="身份: guest/member/manager/superior/admin")
    status = db.Column(db.Integer, default=1, comment="状态: 0=禁用, 1=正常")
    login_ip = db.Column(db.String(128), comment="最后登录IP")
    login_date = db.Column(db.DateTime, comment="最后登录时间")
    is_admin = db.Column(db.Integer, default=0, comment="是否超级管理员: 0=否, 1=是")
    deleted = db.Column(db.Integer, default=0, comment="逻辑删除")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    dept = db.relationship("Dept", backref="users")

    def __repr__(self):
        return f"<SysUser {self.username}>"
