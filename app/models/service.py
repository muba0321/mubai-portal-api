from datetime import datetime
from app.extensions import db


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)
    owner = db.Column(db.String(64))
    url = db.Column(db.String(256))
    status = db.Column(db.String(32), default="running")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Service {self.name}>"
