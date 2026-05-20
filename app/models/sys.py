from datetime import datetime
from app.extensions import db


class SysMonitor(db.Model):
    __tablename__ = "sys_monitor"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    server_online = db.Column(db.Integer, nullable=False, default=0)
    service_running = db.Column(db.Integer, nullable=False, default=0)
    network_status = db.Column(db.String(20), nullable=False, default="normal")
    storage_usage = db.Column(db.String(20), nullable=True)
    alert_pending = db.Column(db.Integer, nullable=False, default=0)
    cpu_load = db.Column(db.String(20), nullable=True)
    snapshot_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f"<SysMonitor {self.snapshot_time}>"


class SysCommonLink(db.Model):
    __tablename__ = "sys_common_link"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    url = db.Column(db.String(500), nullable=False)
    icon = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    sort = db.Column(db.Integer, nullable=False, default=0)
    enabled = db.Column(db.SmallInteger, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<SysCommonLink {self.title}>"


class SysRecentVisit(db.Model):
    __tablename__ = "sys_recent_visit"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, nullable=False)
    page_path = db.Column(db.String(200), nullable=False)
    page_title = db.Column(db.String(100), nullable=False)
    visited_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f"<SysRecentVisit {self.user_id}:{self.page_path}>"


class SysUser(db.Model):
    __tablename__ = "sys_user"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(128), nullable=True)
    role = db.Column(db.String(32), nullable=False, default="user")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted = db.Column(db.SmallInteger, nullable=False, default=0)

    def __repr__(self):
        return f"<SysUser {self.username}>"
