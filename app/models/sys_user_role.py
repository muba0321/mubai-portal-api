from app.extensions import db


class UserRole(db.Model):
    """用户-角色关联"""
    __tablename__ = "sys_user_role"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("sys_user.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("sys_role.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "role_id", name="uk_user_role"),
    )

    def __repr__(self):
        return f"<UserRole user_id={self.user_id} role_id={self.role_id}>"
