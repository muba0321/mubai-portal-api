"""
知识库管理模型
"""
from datetime import datetime
from app.extensions import db


class KbFile(db.Model):
    """知识库文件索引"""
    __tablename__ = "kb_files"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    file_path = db.Column(db.String(512), nullable=False, unique=True, comment="相对路径")
    file_name = db.Column(db.String(256), nullable=False, comment="文件名")
    file_ext = db.Column(db.String(10), comment="文件扩展名：md/sh/py/yml/json...")
    title = db.Column(db.String(256), comment="标题（从 frontmatter 提取或文件名）")
    category = db.Column(db.String(64), comment="一级分类")
    sub_category = db.Column(db.String(64), comment="二级分类")
    file_size = db.Column(db.Integer, comment="文件大小（字节）")
    word_count = db.Column(db.Integer, comment="字数统计")
    content_text = db.Column(db.Text, comment="纯文本内容（用于搜索）")
    created_at = db.Column(db.DateTime, comment="文件创建时间")
    modified_at = db.Column(db.DateTime, comment="文件修改时间")
    synced_at = db.Column(db.DateTime, default=datetime.now, comment="同步时间")

    def __repr__(self):
        return f"<KbFile {self.file_name}>"


class KbSyncLog(db.Model):
    """同步日志"""
    __tablename__ = "kb_sync_log"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    started_at = db.Column(db.DateTime, default=datetime.now, comment="开始时间")
    finished_at = db.Column(db.DateTime, comment="结束时间")
    duration_ms = db.Column(db.Integer, comment="耗时（毫秒）")
    files_added = db.Column(db.Integer, default=0, comment="新增文件数")
    files_updated = db.Column(db.Integer, default=0, comment="更新文件数")
    files_deleted = db.Column(db.Integer, default=0, comment="删除文件数")
    status = db.Column(db.String(20), default="success", comment="success / failed")
    error_msg = db.Column(db.Text, comment="错误信息")

    def __repr__(self):
        return f"<KbSyncLog {self.status}>"
