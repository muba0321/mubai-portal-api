from datetime import datetime

from app.extensions import db


class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    todos = db.relationship(
        "TodoItem", backref="project", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Project {self.name}>"


class TodoItem(db.Model):
    __tablename__ = "todo_item"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("todo_item.id", ondelete="CASCADE"), nullable=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="pending")
    priority = db.Column(db.String(16), nullable=False, default="medium")
    assignee = db.Column(db.String(64), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    children = db.relationship(
        "TodoItem",
        backref=db.backref("parent", remote_side=[id]),
        lazy="select",
    )

    def __repr__(self):
        return f"<TodoItem {self.title}>"
