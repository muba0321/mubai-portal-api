"""
知识库管理 API
"""
import os
import re
import time
import subprocess
from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app.extensions import db
from app.utils.response import success, error
from app.models.knowledge_base import KbFile, KbSyncLog

knowledge_bp = Blueprint("knowledge", __name__)

KB_SOURCE = "/mnt/webdav/沐白的知识库/"
KB_TARGET = "/opt/knowledge-base/"
SYNC_SCRIPT = "/opt/scripts/kb-sync.sh"


# ==================== 同步 ====================

@knowledge_bp.route("/sync", methods=["POST"])
@jwt_required()
def trigger_sync():
    """手动触发同步"""
    log = KbSyncLog(started_at=datetime.now())
    db.session.add(log)
    db.session.flush()

    start_time = time.time()
    try:
        result = subprocess.run(
            [SYNC_SCRIPT],
            capture_output=True, text=True, timeout=300
        )
        duration = int((time.time() - start_time) * 1000)

        if result.returncode == 0:
            rsync_log = result.stdout
            files_added = rsync_log.count("created")
            files_updated = rsync_log.count("updated")
            files_deleted = rsync_log.count("deleting")

            log.finished_at = datetime.now()
            log.duration_ms = duration
            log.files_added = files_added
            log.files_updated = files_updated
            log.files_deleted = files_deleted
            log.status = "success"
        else:
            log.finished_at = datetime.now()
            log.duration_ms = duration
            log.status = "failed"
            log.error_msg = result.stderr[:500]

        db.session.commit()
        scan_files()

        return success(data={
            "duration": duration,
            "added": log.files_added,
            "updated": log.files_updated,
            "deleted": log.files_deleted,
        }, msg="同步完成")
    except Exception as e:
        log.finished_at = datetime.now()
        log.duration_ms = int((time.time() - start_time) * 1000)
        log.status = "failed"
        log.error_msg = str(e)
        db.session.commit()
        return error(msg=f"同步失败: {str(e)}")


@knowledge_bp.route("/sync/status", methods=["GET"])
@jwt_required()
def get_sync_status():
    """获取同步状态"""
    logs = KbSyncLog.query.order_by(KbSyncLog.started_at.desc()).limit(10).all()
    last_sync = logs[0] if logs else None

    return success(data={
        "lastSync": {
            "startedAt": last_sync.started_at.strftime("%Y-%m-%d %H:%M:%S") if last_sync else None,
            "duration": last_sync.duration_ms if last_sync else None,
            "status": last_sync.status if last_sync else None,
            "filesAdded": last_sync.files_added if last_sync else 0,
            "filesUpdated": last_sync.files_updated if last_sync else 0,
        },
        "recentLogs": [{
            "startedAt": l.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": l.duration_ms,
            "status": l.status,
            "added": l.files_added,
            "updated": l.files_updated,
            "deleted": l.files_deleted,
        } for l in logs],
    })


# ==================== 目录树 ====================

@knowledge_bp.route("/tree", methods=["GET"])
@jwt_required()
def get_tree():
    """获取目录树（支持任意深度）"""
    files = KbFile.query.order_by(KbFile.file_path).all()

    root = {"name": "", "children": {}, "files": []}

    for f in files:
        parts = f.file_path.split("/")
        node = root
        for i, part in enumerate(parts[:-1]):
            if part not in node["children"]:
                node["children"][part] = {"name": part, "children": {}, "files": []}
            node = node["children"][part]
        node["files"].append({
            "name": f.file_name,
            "path": f.file_path,
            "title": f.title or os.path.splitext(f.file_name)[0],
            "size": f.file_size,
            "wordCount": f.word_count,
            "fileExt": f.file_ext or os.path.splitext(f.file_name)[1].lower(),
        })

    def count_files(node):
        total = len(node["files"])
        for child in node["children"].values():
            total += count_files(child)
        return total

    def to_list(node):
        result = []
        for name in sorted(node["children"].keys()):
            child = node["children"][name]
            result.append({
                "name": name,
                "type": "folder",
                "fileCount": count_files(child),
                "children": to_list(child),
                "files": child["files"],
            })
        result.extend(node["files"])
        return result

    return success(data=to_list(root))


# ==================== 文件列表 ====================

@knowledge_bp.route("/files", methods=["GET"])
@jwt_required()
def list_files():
    """文件列表"""
    category = request.args.get("category", "")
    keyword = request.args.get("keyword", "")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)

    q = KbFile.query
    if category:
        q = q.filter(KbFile.category == category)
    if keyword:
        q = q.filter(
            db.or_(
                KbFile.title.like(f"%{keyword}%"),
                KbFile.file_name.like(f"%{keyword}%"),
                KbFile.content_text.like(f"%{keyword}%"),
            )
        )

    total = q.count()
    files = q.order_by(KbFile.modified_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return success(data={
        "list": [{
            "id": f.id,
            "path": f.file_path,
            "name": f.file_name,
            "title": f.title or os.path.splitext(f.file_name)[0],
            "category": f.category,
            "subCategory": f.sub_category,
            "size": f.file_size,
            "wordCount": f.word_count,
            "fileExt": f.file_ext or os.path.splitext(f.file_name)[1].lower(),
            "modifiedAt": f.modified_at.strftime("%Y-%m-%d %H:%M:%S") if f.modified_at else None,
        } for f in files],
        "total": total,
        "page": page,
        "pageSize": page_size,
    })


# ==================== 文件内容 ====================

@knowledge_bp.route("/files/<path:file_path>", methods=["GET"])
@jwt_required()
def get_file_content(file_path):
    """获取文件内容"""
    kb_file = KbFile.query.filter_by(file_path=file_path).first()

    full_path = os.path.join(KB_TARGET, file_path)
    content = ""
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    file_ext = kb_file.file_ext if kb_file else os.path.splitext(file_path)[1].lower()

    return success(data={
        "id": kb_file.id if kb_file else None,
        "path": file_path,
        "name": os.path.basename(file_path),
        "title": kb_file.title if kb_file else os.path.splitext(os.path.basename(file_path))[0],
        "category": kb_file.category if kb_file else "",
        "subCategory": kb_file.sub_category if kb_file else "",
        "content": content,
        "size": kb_file.file_size if kb_file else os.path.getsize(full_path) if os.path.exists(full_path) else 0,
        "wordCount": kb_file.word_count if kb_file else 0,
        "fileExt": file_ext,
        "modifiedAt": kb_file.modified_at.strftime("%Y-%m-%d %H:%M:%S") if kb_file and kb_file.modified_at else None,
    })


# ==================== 搜索 ====================

@knowledge_bp.route("/search", methods=["GET"])
@jwt_required()
def search_files():
    """全文搜索"""
    keyword = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    limit = request.args.get("limit", 50, type=int)

    if not keyword:
        return success(data=[])

    q = KbFile.query.filter(
        db.or_(
            KbFile.title.like(f"%{keyword}%"),
            KbFile.file_name.like(f"%{keyword}%"),
            KbFile.content_text.like(f"%{keyword}%"),
        )
    )
    if category:
        q = q.filter(KbFile.category == category)

    files = q.order_by(KbFile.modified_at.desc()).limit(limit).all()

    return success(data=[{
        "path": f.file_path,
        "name": f.file_name,
        "title": f.title or os.path.splitext(f.file_name)[0],
        "category": f.category,
        "subCategory": f.sub_category,
        "wordCount": f.word_count,
        "fileExt": f.file_ext or os.path.splitext(f.file_name)[1].lower(),
        "modifiedAt": f.modified_at.strftime("%Y-%m-%d %H:%M:%S") if f.modified_at else None,
    } for f in files])


# ==================== 统计 ====================

@knowledge_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    """统计概览"""
    total_files = KbFile.query.count()
    total_words = db.session.query(func.sum(KbFile.word_count)).scalar() or 0
    categories = db.session.query(
        KbFile.category, func.count(KbFile.id)
    ).group_by(KbFile.category).all()

    return success(data={
        "totalFiles": total_files,
        "totalWords": total_words,
        "categories": [{"name": c[0], "count": c[1]} for c in sorted(categories, key=lambda x: -x[1])],
    })


# ==================== 辅助函数 ====================

# 支持的文件类型
SUPPORTED_EXTS = {
    ".md", ".sh", ".py", ".yml", ".yaml", ".json", ".txt",
    ".conf", ".cfg", ".ini", ".log", ".sql", ".js", ".ts",
    ".env", ".toml", ".xml", ".csv",
}

def scan_files():
    """扫描文件系统，更新文件索引"""
    added = 0
    updated = 0

    for root, dirs, files in os.walk(KB_TARGET):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for fname in files:
            _, ext = os.path.splitext(fname)
            if ext.lower() not in SUPPORTED_EXTS:
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, KB_TARGET)

            try:
                stat = os.stat(full_path)
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                # 提取标题
                title = os.path.splitext(fname)[0]
                if ext.lower() == ".md":
                    fm_match = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
                    if fm_match:
                        title = fm_match.group(1).strip().strip('"').strip("'")

                word_count = len(re.findall(r"[\w一-鿿]+", content))

                parts = rel_path.split("/")
                category = parts[0] if parts else ""
                sub_category = parts[1] if len(parts) > 1 else ""

                kb_file = KbFile.query.filter_by(file_path=rel_path).first()
                if kb_file:
                    kb_file.title = title
                    kb_file.file_ext = ext.lower()
                    kb_file.file_size = stat.st_size
                    kb_file.word_count = word_count
                    kb_file.content_text = content[:50000]
                    kb_file.modified_at = datetime.fromtimestamp(stat.st_mtime)
                    kb_file.synced_at = datetime.now()
                    updated += 1
                else:
                    kb_file = KbFile(
                        file_path=rel_path,
                        file_name=fname,
                        file_ext=ext.lower(),
                        title=title,
                        category=category,
                        sub_category=sub_category,
                        file_size=stat.st_size,
                        word_count=word_count,
                        content_text=content[:50000],
                        modified_at=datetime.fromtimestamp(stat.st_mtime),
                        synced_at=datetime.now(),
                    )
                    db.session.add(kb_file)
                    added += 1
            except Exception:
                continue

    if added or updated:
        db.session.commit()
