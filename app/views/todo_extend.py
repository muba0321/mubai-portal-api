"""
待办功能扩展 API
附件上传/下载、评论、标签、看板视图、日历视图、统计
"""
import os
import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.todo_extend import TodoAttachment, TodoComment, TodoTag, TodoItemTag
from app.models.todo import TodoItem, Project
from app.utils.response import success, error

logger = logging.getLogger("sre-portal")

todo_extend_bp = Blueprint("todo_extend", __name__)

# 上传配置
UPLOAD_FOLDER = "/uploads/todo"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "doc", "docx", "xls", "xlsx", "txt", "log", "zip"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_current_user():
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    from app.models.sys_user import SysUser
    user = SysUser.query.get(user_id)
    return user.username if user else "admin"


# ==================== 附件管理 ====================

@todo_extend_bp.route("/todos/<int:todo_id>/attachments", methods=["POST"])
@jwt_required()
def upload_attachment(todo_id):
    """上传附件"""
    todo = TodoItem.query.get(todo_id)
    if not todo:
        return error(msg="任务不存在")

    if "file" not in request.files:
        return error(msg="请选择文件")

    file = request.files["file"]
    if file.filename == "":
        return error(msg="文件名为空")

    if not allowed_file(file.filename):
        return error(msg=f"不支持的文件类型，仅支持：{', '.join(ALLOWED_EXTENSIONS)}")

    # 创建上传目录
    upload_dir = os.path.join(current_app.root_path, "..", UPLOAD_FOLDER, str(todo_id))
    os.makedirs(upload_dir, exist_ok=True)

    # 保存文件
    filename = secure_filename(file.filename)
    # 添加时间戳避免重名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)
    filename = f"{name}_{timestamp}{ext}"

    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    # 记录到数据库
    attachment = TodoAttachment(
        todo_id=todo_id,
        file_name=file.filename,  # 原始文件名
        file_path=f"/uploads/todo/{todo_id}/{filename}",
        file_size=os.path.getsize(file_path),
        file_type=ext.lstrip("."),
        uploaded_by=get_current_user(),
    )
    db.session.add(attachment)
    db.session.commit()

    return success(data={
        "id": attachment.id,
        "fileName": attachment.file_name,
        "filePath": attachment.file_path,
        "fileSize": attachment.file_size,
        "fileType": attachment.file_type,
        "url": f"/api/v1/todo/attachments/{attachment.id}",
    }, msg="上传成功")


@todo_extend_bp.route("/todos/<int:todo_id>/attachments", methods=["GET"])
@jwt_required()
def list_attachments(todo_id):
    """获取附件列表"""
    attachments = TodoAttachment.query.filter_by(todo_id=todo_id).order_by(TodoAttachment.created_at.desc()).all()
    return success(data=[{
        "id": a.id,
        "fileName": a.file_name,
        "filePath": a.file_path,
        "fileSize": a.file_size,
        "fileType": a.file_type,
        "uploadedBy": a.uploaded_by,
        "createdAt": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else None,
    } for a in attachments])


@todo_extend_bp.route("/attachments/<int:attachment_id>", methods=["GET"])
@jwt_required()
def download_attachment(attachment_id):
    """下载附件"""
    attachment = TodoAttachment.query.get(attachment_id)
    if not attachment:
        return error(msg="附件不存在")

    # 解析文件路径
    base_dir = os.path.join(current_app.root_path, "..")
    file_path = os.path.join(base_dir, attachment.file_path.lstrip("/"))

    if not os.path.exists(file_path):
        return error(msg="文件不存在")

    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)

    return send_from_directory(directory, filename, as_attachment=True, download_name=attachment.file_name)


@todo_extend_bp.route("/attachments/<int:attachment_id>", methods=["DELETE"])
@jwt_required()
def delete_attachment(attachment_id):
    """删除附件"""
    attachment = TodoAttachment.query.get(attachment_id)
    if not attachment:
        return error(msg="附件不存在")

    # 删除文件
    base_dir = os.path.join(current_app.root_path, "..")
    file_path = os.path.join(base_dir, attachment.file_path.lstrip("/"))
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(attachment)
    db.session.commit()

    return success(msg="删除成功")


# ==================== 评论功能 ====================

@todo_extend_bp.route("/todos/<int:todo_id>/comments", methods=["POST"])
@jwt_required()
def add_comment(todo_id):
    """发表评论"""
    todo = TodoItem.query.get(todo_id)
    if not todo:
        return error(msg="任务不存在")

    data = request.get_json()
    content = data.get("content", "").strip()
    if not content:
        return error(msg="评论内容不能为空")

    comment = TodoComment(
        todo_id=todo_id,
        content=content,
        created_by=get_current_user(),
    )
    db.session.add(comment)
    db.session.commit()

    return success(data={
        "id": comment.id,
        "content": comment.content,
        "createdBy": comment.created_by,
        "createdAt": comment.created_at.strftime("%Y-%m-%d %H:%M:%S") if comment.created_at else None,
    }, msg="评论成功")


@todo_extend_bp.route("/todos/<int:todo_id>/comments", methods=["GET"])
@jwt_required()
def list_comments(todo_id):
    """获取评论列表"""
    comments = TodoComment.query.filter_by(todo_id=todo_id).order_by(TodoComment.created_at.asc()).all()
    return success(data=[{
        "id": c.id,
        "content": c.content,
        "createdBy": c.created_by,
        "createdAt": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else None,
    } for c in comments])


@todo_extend_bp.route("/comments/<int:comment_id>", methods=["PUT"])
@jwt_required()
def update_comment(comment_id):
    """编辑评论"""
    comment = TodoComment.query.get(comment_id)
    if not comment:
        return error(msg="评论不存在")

    data = request.get_json()
    content = data.get("content", "").strip()
    if not content:
        return error(msg="评论内容不能为空")

    comment.content = content
    db.session.commit()

    return success(msg="更新成功")


@todo_extend_bp.route("/comments/<int:comment_id>", methods=["DELETE"])
@jwt_required()
def delete_comment(comment_id):
    """删除评论"""
    comment = TodoComment.query.get(comment_id)
    if not comment:
        return error(msg="评论不存在")

    db.session.delete(comment)
    db.session.commit()

    return success(msg="删除成功")


# ==================== 标签管理 ====================

@todo_extend_bp.route("/tags", methods=["GET"])
@jwt_required()
def list_tags():
    """获取标签列表"""
    tags = TodoTag.query.order_by(TodoTag.name).all()
    return success(data=[{
        "id": t.id,
        "name": t.name,
        "color": t.color,
    } for t in tags])


@todo_extend_bp.route("/tags", methods=["POST"])
@jwt_required()
def create_tag():
    """创建标签"""
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return error(msg="标签名称不能为空")

    # 检查是否已存在
    existing = TodoTag.query.filter_by(name=name).first()
    if existing:
        return error(msg="标签已存在")

    tag = TodoTag(name=name, color=data.get("color", "#409eff"))
    db.session.add(tag)
    db.session.commit()

    return success(data={"id": tag.id, "name": tag.name, "color": tag.color}, msg="创建成功")


@todo_extend_bp.route("/tags/<int:tag_id>", methods=["PUT"])
@jwt_required()
def update_tag(tag_id):
    """更新标签"""
    tag = TodoTag.query.get(tag_id)
    if not tag:
        return error(msg="标签不存在")

    data = request.get_json()
    if "name" in data:
        tag.name = data["name"]
    if "color" in data:
        tag.color = data["color"]

    db.session.commit()
    return success(msg="更新成功")


@todo_extend_bp.route("/tags/<int:tag_id>", methods=["DELETE"])
@jwt_required()
def delete_tag(tag_id):
    """删除标签"""
    tag = TodoTag.query.get(tag_id)
    if not tag:
        return error(msg="标签不存在")

    # 删除关联关系
    TodoItemTag.query.filter_by(tag_id=tag_id).delete()
    db.session.delete(tag)
    db.session.commit()

    return success(msg="删除成功")


@todo_extend_bp.route("/todos/<int:todo_id>/tags", methods=["POST"])
@jwt_required()
def add_todo_tag(todo_id):
    """为任务添加标签"""
    todo = TodoItem.query.get(todo_id)
    if not todo:
        return error(msg="任务不存在")

    data = request.get_json()
    tag_id = data.get("tag_id")
    if not tag_id:
        return error(msg="标签 ID 不能为空")

    tag = TodoTag.query.get(tag_id)
    if not tag:
        return error(msg="标签不存在")

    # 检查是否已添加
    existing = TodoItemTag.query.filter_by(todo_id=todo_id, tag_id=tag_id).first()
    if existing:
        return error(msg="标签已添加")

    relation = TodoItemTag(todo_id=todo_id, tag_id=tag_id)
    db.session.add(relation)
    db.session.commit()

    return success(msg="添加成功")


@todo_extend_bp.route("/todos/<int:todo_id>/tags/<int:tag_id>", methods=["DELETE"])
@jwt_required()
def remove_todo_tag(todo_id, tag_id):
    """移除任务标签"""
    relation = TodoItemTag.query.filter_by(todo_id=todo_id, tag_id=tag_id).first()
    if not relation:
        return error(msg="标签关联不存在")

    db.session.delete(relation)
    db.session.commit()

    return success(msg="移除成功")


@todo_extend_bp.route("/todos/<int:todo_id>/tags", methods=["GET"])
@jwt_required()
def get_todo_tags(todo_id):
    """获取任务的标签列表"""
    relations = TodoItemTag.query.filter_by(todo_id=todo_id).all()
    tag_ids = [r.tag_id for r in relations]
    tags = TodoTag.query.filter(TodoTag.id.in_(tag_ids)).all()

    return success(data=[{
        "id": t.id,
        "name": t.name,
        "color": t.color,
    } for t in tags])


# ==================== 增强的任务查询 ====================

@todo_extend_bp.route("/todos", methods=["GET"])
@jwt_required()
def list_todos_enhanced():
    """增强版任务列表（支持多条件筛选）"""
    # 获取筛选参数
    project_id = request.args.get("projectId", type=int)
    assignee = request.args.get("assignee")
    priority = request.args.get("priority")
    status = request.args.get("status")
    tag_id = request.args.get("tagId", type=int)
    keyword = request.args.get("keyword")
    due_date_start = request.args.get("dueDateStart")
    due_date_end = request.args.get("dueDateEnd")

    # 构建查询
    q = TodoItem.query

    if project_id:
        q = q.filter_by(project_id=project_id)
    if assignee:
        q = q.filter(TodoItem.assignee.like(f"%{assignee}%"))
    if priority:
        q = q.filter_by(priority=priority)
    if status:
        q = q.filter_by(status=status)
    if keyword:
        q = q.filter(TodoItem.title.like(f"%{keyword}%"))
    if due_date_start:
        q = q.filter(TodoItem.due_date >= datetime.fromisoformat(due_date_start))
    if due_date_end:
        q = q.filter(TodoItem.due_date <= datetime.fromisoformat(due_date_end))
    if tag_id:
        todo_ids = [r.todo_id for r in TodoItemTag.query.filter_by(tag_id=tag_id).all()]
        q = q.filter(TodoItem.id.in_(todo_ids))

    todos = q.order_by(TodoItem.view_order, TodoItem.created_at.desc()).all()

    # 为每个任务获取标签
    result = []
    for todo in todos:
        tag_relations = TodoItemTag.query.filter_by(todo_id=todo.id).all()
        tags = TodoTag.query.filter(TodoTag.id.in_([r.tag_id for r in tag_relations])).all()

        result.append({
            "id": todo.id,
            "projectId": todo.project_id,
            "parentId": todo.parent_id,
            "title": todo.title,
            "description": todo.description,
            "status": todo.status,
            "priority": todo.priority,
            "assignee": todo.assignee,
            "dueDate": todo.due_date.strftime("%Y-%m-%d %H:%M:%S") if todo.due_date else None,
            "viewOrder": todo.view_order,
            "estimatedHours": float(todo.estimated_hours) if todo.estimated_hours else None,
            "actualHours": float(todo.actual_hours) if todo.actual_hours else None,
            "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tags],
            "createdAt": todo.created_at.strftime("%Y-%m-%d %H:%M:%S") if todo.created_at else None,
            "updatedAt": todo.updated_at.strftime("%Y-%m-%d %H:%M:%S") if todo.updated_at else None,
        })

    return success(data=result)


@todo_extend_bp.route("/kanban", methods=["GET"])
@jwt_required()
def get_kanban():
    """获取看板视图数据（按状态分组）"""
    project_id = request.args.get("projectId", type=int)

    q = TodoItem.query
    if project_id:
        q = q.filter_by(project_id=project_id)

    todos = q.order_by(TodoItem.view_order, TodoItem.created_at.desc()).all()

    # 按状态分组
    kanban = {
        "pending": [],
        "in_progress": [],
        "completed": [],
        "cancelled": [],
    }

    for todo in todos:
        if todo.status in kanban:
            # 获取标签
            tag_relations = TodoItemTag.query.filter_by(todo_id=todo.id).all()
            tags = TodoTag.query.filter(TodoTag.id.in_([r.tag_id for r in tag_relations])).all()

            kanban[todo.status].append({
                "id": todo.id,
                "title": todo.title,
                "priority": todo.priority,
                "assignee": todo.assignee,
                "dueDate": todo.due_date.strftime("%Y-%m-%d") if todo.due_date else None,
                "viewOrder": todo.view_order,
                "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tags],
                "attachmentCount": TodoAttachment.query.filter_by(todo_id=todo.id).count(),
                "commentCount": TodoComment.query.filter_by(todo_id=todo.id).count(),
            })

    return success(data=kanban)


@todo_extend_bp.route("/calendar", methods=["GET"])
@jwt_required()
def get_calendar():
    """获取日历视图数据（按截止日期）"""
    project_id = request.args.get("projectId", type=int)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not year or not month:
        now = datetime.now()
        year = now.year
        month = now.month

    # 计算月份范围
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    q = TodoItem.query.filter(
        TodoItem.due_date >= start_date,
        TodoItem.due_date < end_date,
    )

    if project_id:
        q = q.filter_by(project_id=project_id)

    todos = q.all()

    # 按日期分组
    calendar = {}
    for todo in todos:
        date_key = todo.due_date.strftime("%Y-%m-%d")
        if date_key not in calendar:
            calendar[date_key] = []

        calendar[date_key].append({
            "id": todo.id,
            "title": todo.title,
            "priority": todo.priority,
            "status": todo.status,
            "assignee": todo.assignee,
        })

    return success(data={"year": year, "month": month, "events": calendar})


@todo_extend_bp.route("/statistics", methods=["GET"])
@jwt_required()
def get_statistics():
    """获取统计数据"""
    project_id = request.args.get("projectId", type=int)

    q = TodoItem.query
    if project_id:
        q = q.filter_by(project_id=project_id)

    todos = q.all()

    # 状态统计
    status_stats = {}
    for todo in todos:
        status_stats[todo.status] = status_stats.get(todo.status, 0) + 1

    # 优先级统计
    priority_stats = {}
    for todo in todos:
        priority_stats[todo.priority] = priority_stats.get(todo.priority, 0) + 1

    # 负责人统计
    assignee_stats = {}
    for todo in todos:
        if todo.assignee:
            if todo.assignee not in assignee_stats:
                assignee_stats[todo.assignee] = {"total": 0, "completed": 0}
            assignee_stats[todo.assignee]["total"] += 1
            if todo.status == "completed":
                assignee_stats[todo.assignee]["completed"] += 1

    # 近 30 天完成趋势
    trend = []
    for i in range(29, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date()
        completed = sum(1 for t in todos if t.status == "completed" and t.updated_at and t.updated_at.date() == date)
        trend.append({"date": date.strftime("%Y-%m-%d"), "completed": completed})

    return success(data={
        "statusStats": status_stats,
        "priorityStats": priority_stats,
        "assigneeStats": assignee_stats,
        "trend": trend,
        "total": len(todos),
    })


@todo_extend_bp.route("/todos/<int:todo_id>/view-order", methods=["PUT"])
@jwt_required()
def update_view_order(todo_id):
    """更新看板排序"""
    todo = TodoItem.query.get(todo_id)
    if not todo:
        return error(msg="任务不存在")

    data = request.get_json()
    view_order = data.get("viewOrder")
    if view_order is None:
        return error(msg="排序值不能为空")

    todo.view_order = view_order
    db.session.commit()

    return success(msg="更新成功")
