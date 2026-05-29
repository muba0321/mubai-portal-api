from datetime import datetime
from app.extensions import db


class CmdbVM(db.Model):
    __tablename__ = "cmdb_vm"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    cluster = db.Column(db.String(100), nullable=False)
    external_ip = db.Column(db.String(45), nullable=False)
    internal_ip = db.Column(db.String(45), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    status = db.Column(db.SmallInteger, nullable=False, default=1)
    tenant = db.Column(db.String(100), nullable=False)
    vcpus = db.Column(db.Integer, nullable=False, default=4)
    memory = db.Column(db.Integer, nullable=False, default=8192)
    disk = db.Column(db.String(50), nullable=True)
    access_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    created_by = db.Column(db.String(64), nullable=True)
    updated_by = db.Column(db.String(64), nullable=True)
    deleted = db.Column(db.SmallInteger, nullable=False, default=0)

    def __repr__(self):
        return f"<CmdbVM {self.name}>"
