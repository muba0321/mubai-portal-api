"""
待办相关模型（扩展）
"""
from datetime import datetime
from app.extensions import db


class TodoAttachment(db.Model):
    """任务附件"""
    __tablename__ = "todo_attachment"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    todo_id = db.Column(db.Integer, db.ForeignKey("todo_item.id", ondelete="CASCADE"), nullable=False, comment="关联待办项 ID")
    file_name = db.Column(db.String(255), nullable=False, comment="文件名")
    file_path = db.Column(db.String(500), nullable=False, comment="文件路径")
    file_size = db.Column(db.Integer, comment="文件大小 (bytes)")
    file_type = db.Column(db.String(50), comment="文件类型 (image/pdf/doc)")
    uploaded_by = db.Column(db.String(64), comment="上传人")
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<TodoAttachment {self.file_name}>"


class TodoComment(db.Model):
    """任务评论"""
    __tablename__ = "todo_comment"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    todo_id = db.Column(db.Integer, db.ForeignKey("todo_item.id", ondelete="CASCADE"), nullable=False, comment="关联待办项 ID")
    content = db.Column(db.Text, nullable=False, comment="评论内容")
    created_by = db.Column(db.String(64), comment="创建人")
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<TodoComment {self.id}>"


class TodoTag(db.Model):
    """任务标签"""
    __tablename__ = "todo_tag"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, unique=True, comment="标签名称")
    color = db.Column(db.String(7), comment="标签颜色 (#ff0000)")
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<TodoTag {self.name}>"


class TodoItemTag(db.Model):
    """任务 - 标签关联"""
    __tablename__ = "todo_item_tag"

    todo_id = db.Column(db.Integer, db.ForeignKey("todo_item.id", ondelete="CASCADE"), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey("todo_tag.id", ondelete="CASCADE"), primary_key=True)
