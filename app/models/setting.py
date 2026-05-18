from datetime import datetime
from app.extensions import db


class SysSetting(db.Model):
    __tablename__ = "sys_setting"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    setting_key = db.Column(db.String(128), nullable=False, unique=True)
    setting_group = db.Column(db.String(64), nullable=False)
    setting_type = db.Column(db.String(32), nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    default_value = db.Column(db.Text, nullable=True)
    label = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<SysSetting {self.setting_key}>"
