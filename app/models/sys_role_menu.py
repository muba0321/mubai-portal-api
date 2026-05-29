from app.extensions import db


class RoleMenu(db.Model):
    """角色-菜单权限关联"""
    __tablename__ = "sys_role_menu"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("sys_role.id"), nullable=False)
    menu_id = db.Column(db.Integer, db.ForeignKey("sys_menu.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("role_id", "menu_id", name="uk_role_menu"),
    )

    def __repr__(self):
        return f"<RoleMenu role_id={self.role_id} menu_id={self.menu_id}>"
