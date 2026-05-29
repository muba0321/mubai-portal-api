from datetime import datetime
from app.extensions import db


class ConfigEntry(db.Model):
    __tablename__ = "sys_config"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    namespace = db.Column(db.String(64), nullable=False, index=True)
    config_key = db.Column(db.String(128), nullable=False)
    config_value = db.Column(db.Text, nullable=True)
    config_type = db.Column(db.String(32), nullable=True, default="string")
    remark = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("namespace", "config_key", name="uq_namespace_config_key"),
    )

    def __repr__(self):
        return f"<ConfigEntry {self.namespace}:{self.config_key}>"
