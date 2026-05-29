from datetime import datetime
from app.extensions import db


class Menu(db.Model):
    """菜单/按钮权限（树形结构）"""
    __tablename__ = "sys_menu"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, default=0, comment="父菜单ID, 0=顶级")
    name = db.Column(db.String(64), nullable=False, comment="菜单名称")
    code = db.Column(db.String(128), comment="权限标识, 如 sys:user:create")
    type = db.Column(db.String(16), nullable=False, comment="类型: C=目录, M=菜单, B=按钮")
    path = db.Column(db.String(256), comment="路由路径")
    icon = db.Column(db.String(64), comment="图标")
    sort = db.Column(db.Integer, default=0, comment="排序")
    visible = db.Column(db.Integer, default=1, comment="是否可见: 0=隐藏, 1=显示")
    status = db.Column(db.Integer, default=1, comment="状态: 0=停用, 1=正常")
    component = db.Column(db.String(256), comment="组件路径")
    redirect = db.Column(db.String(256), comment="重定向路径")
    always_show = db.Column(db.Integer, default=0, comment="始终显示")
    keep_alive = db.Column(db.Integer, default=0, comment="缓存")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Menu {self.name}>"
