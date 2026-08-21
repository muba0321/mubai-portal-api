"""
需求管理 API
由 todo API 升级而来
"""
import json
import logging
from datetime import datetime
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.utils.response import success, error
from app.models.requirement import Project, Requirement, Milestone, RequirementCommit
from app.models.requirement_extend import (
    RequirementAttachment, RequirementComment, RequirementLabel, RequirementLabelMap,
    RequirementVersion, RequirementActivity,
    ReqApprovalTemplate, ReqApprovalTemplateNode, ReqApprovalInstance, ReqApprovalRecord,
)
from app.models.sys_user import SysUser

logger = logging.getLogger("sre-portal")

requirement_bp = Blueprint("requirement", __name__)

# 状态机定义
VALID_TRANSITIONS = {
    "proposed": ["under_review", "rejected"],
    "under_review": ["approved", "rejected"],
    "approved": ["in_progress", "rejected"],
    "in_progress": ["in_testing", "blocked", "rejected"],
    "blocked": ["in_progress"],
    "in_testing": ["done", "re_testing", "in_progress"],
    "re_testing": ["done", "in_progress"],
    "done": [],
    "rejected": [],
}

STATUS_CATEGORIES = {
    "backlog": ["proposed"],
    "in_review": ["under_review"],
    "planned": ["approved"],
    "in_progress": ["in_progress", "blocked"],
    "testing": ["in_testing", "re_testing"],
    "completed": ["done"],
    "canceled": ["rejected"],
}


def _get_current_user_id():
    """获取当前用户 ID"""
    try:
        identity = get_jwt_identity()
        return int(identity) if isinstance(identity, str) else identity
    except:
        return None


# ==================== 项目 CRUD ====================

@requirement_bp.route("/projects", methods=["GET"])
@jwt_required()
def list_projects():
    """项目列表"""
    status_filter = request.args.get("status", "")
    q = Project.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    projects = q.order_by(Project.sort.asc(), Project.created_at.desc()).all()
    return success(data=[{
        "id": p.id, "name": p.name, "description": p.description,
        "status": p.status, "sort": p.sort,
        "createdAt": p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    } for p in projects])


@requirement_bp.route("/projects", methods=["POST"])
@jwt_required()
def create_project():
    """创建项目"""
    data = request.get_json()
    if not data or not data.get("name"):
        return error(msg="项目名称不能为空")
    if Project.query.filter_by(name=data["name"]).first():
        return error(msg="项目名称已存在")
    project = Project(name=data["name"], description=data.get("description", ""))
    db.session.add(project)
    db.session.commit()
    return success(data={"id": project.id}, msg="创建成功")


@requirement_bp.route("/projects/<int:project_id>", methods=["PUT"])
@jwt_required()
def update_project(project_id):
    """更新项目"""
    project = Project.query.get(project_id)
    if not project:
        return error(msg="项目不存在")
    data = request.get_json()
    if "name" in data:
        project.name = data["name"]
    if "description" in data:
        project.description = data["description"]
    if "status" in data:
        project.status = data["status"]
    db.session.commit()
    return success(msg="更新成功")


@requirement_bp.route("/projects/<int:project_id>", methods=["DELETE"])
@jwt_required()
def delete_project(project_id):
    """删除项目"""
    project = Project.query.get(project_id)
    if not project:
        return error(msg="项目不存在")
    db.session.delete(project)
    db.session.commit()
    return success(msg="删除成功")


@requirement_bp.route("/projects/sort", methods=["PUT"])
@jwt_required()
def update_projects_sort():
    """批量更新项目排序"""
    data = request.get_json()
    if not data or not isinstance(data, list):
        return error(msg="请求数据格式错误")

    for item in data:
        if "id" not in item or "sort" not in item:
            continue
        project = Project.query.get(item["id"])
        if project:
            project.sort = item["sort"]

    db.session.commit()
    return success(msg="排序已更新")


# ==================== 需求 CRUD ====================

@requirement_bp.route("/", methods=["GET"])
@jwt_required()
def list_requirements():
    """需求列表（支持多条件筛选）"""
    project_id = request.args.get("projectId", type=int)
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    requirement_type = request.args.get("type", "")
    assignee = request.args.get("assignee", "")
    keyword = request.args.get("keyword", "")
    milestone_id = request.args.get("milestoneId", type=int)

    q = Requirement.query.filter_by(deleted_at=None, parent_id=None)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    if priority:
        q = q.filter_by(priority=priority)
    if requirement_type:
        q = q.filter_by(requirement_type=requirement_type)
    if assignee:
        q = q.filter_by(assignee=assignee)
    if milestone_id:
        q = q.filter_by(milestone_id=milestone_id)
    if keyword:
        q = q.filter(Requirement.title.like(f"%{keyword}%"))

    requirements = q.order_by(Requirement.view_order.asc(), Requirement.created_at.desc()).all()

    # 构建子需求映射
    children_map = {}
    all_reqs = Requirement.query.filter_by(deleted_at=None).order_by(Requirement.view_order.asc()).all()
    for r in all_reqs:
        if r.parent_id and r.parent_id in {req.id for req in requirements}:
            if r.parent_id not in children_map:
                children_map[r.parent_id] = []
            children_map[r.parent_id].append({
                "id": r.id,
                "projectId": r.project_id,
                "parentId": r.parent_id,
                "title": r.title,
                "description": r.description,
                "requirementType": r.requirement_type,
                "priority": r.priority,
                "status": r.status,
                "reporterId": r.reporter_id,
                "assignee": r.assignee,
                "assigneeId": r.assignee_id,
                "milestoneId": r.milestone_id,
                "dueDate": r.due_date.strftime("%Y-%m-%d %H:%M:%S") if r.due_date else None,
                "estimatedEffort": r.estimated_effort,
                "tags": r.tags or [],
                "viewOrder": r.view_order,
                "version": r.version,
                "createdAt": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "updatedAt": r.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

    result = []
    for r in requirements:
        item = {
            "id": r.id,
            "projectId": r.project_id,
            "parentId": r.parent_id,
            "title": r.title,
            "description": r.description,
            "requirementType": r.requirement_type,
            "priority": r.priority,
            "status": r.status,
            "reporterId": r.reporter_id,
            "assignee": r.assignee,
            "assigneeId": r.assignee_id,
            "milestoneId": r.milestone_id,
            "dueDate": r.due_date.strftime("%Y-%m-%d %H:%M:%S") if r.due_date else None,
            "estimatedEffort": r.estimated_effort,
            "tags": r.tags or [],
            "viewOrder": r.view_order,
            "version": r.version,
            "createdAt": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updatedAt": r.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if r.id in children_map:
            item["children"] = children_map[r.id]
            item["hasChildren"] = True
        result.append(item)
    return success(data=result)


@requirement_bp.route("/", methods=["POST"])
@jwt_required()
def create_requirement():
    """创建需求"""
    data = request.get_json()
    if not data or not data.get("title") or not data.get("projectId"):
        return error(msg="标题和项目不能为空")

    user_id = _get_current_user_id()
    req = Requirement(
        project_id=data["projectId"],
        title=data["title"],
        description=data.get("description", ""),
        requirement_type=data.get("requirementType", "task"),
        priority=data.get("priority", "P2"),
        status="proposed",
        reporter_id=user_id,
        assignee=data.get("assignee"),
        assignee_id=data.get("assigneeId"),
        milestone_id=data.get("milestoneId"),
        due_date=datetime.strptime(data["dueDate"], "%Y-%m-%d %H:%M:%S") if data.get("dueDate") else None,
        estimated_effort=data.get("estimatedEffort"),
        tags=data.get("tags", []),
    )
    db.session.add(req)
    db.session.commit()

    # 记录活动日志
    _log_activity(req.id, user_id, "create", None, None, json.dumps({"title": req.title}))

    return success(data={"id": req.id}, msg="创建成功")


@requirement_bp.route("/<int:req_id>", methods=["GET", "PUT"])
@jwt_required()
def get_or_update_requirement(req_id):
    """获取或更新需求"""
    req = Requirement.query.get(req_id)
    if not req:
        return error(msg="需求不存在")

    if request.method == "GET":
        return success(data={
            "id": req.id,
            "projectId": req.project_id,
            "parentId": req.parent_id,
            "title": req.title,
            "description": req.description,
            "requirementType": req.requirement_type,
            "priority": req.priority,
            "status": req.status,
            "reporterId": req.reporter_id,
            "assignee": req.assignee,
            "assigneeId": req.assignee_id,
            "milestoneId": req.milestone_id,
            "dueDate": req.due_date.strftime("%Y-%m-%d %H:%M:%S") if req.due_date else None,
            "estimatedEffort": req.estimated_effort,
            "tags": req.tags or [],
            "viewOrder": req.view_order,
            "version": req.version,
            "createdAt": req.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updatedAt": req.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # PUT: update requirement
    data = request.get_json()
    user_id = _get_current_user_id()
    changes = []

    for field in ["title", "description", "requirementType", "priority", "status",
                   "assignee", "assigneeId", "milestoneId", "dueDate", "estimatedEffort", "tags"]:
        if field in data:
            old_val = getattr(req, field if field != "requirementType" else "requirement_type")
            if field == "dueDate" and data[field]:
                new_val = datetime.strptime(data[field], "%Y-%m-%d %H:%M:%S")
            elif field == "tags":
                new_val = json.dumps(data[field]) if isinstance(data[field], list) else data[field]
            else:
                new_val = data[field]

            setattr(req, field if field != "requirementType" else "requirement_type", new_val)
            if str(old_val) != str(new_val):
                changes.append({"field": field, "old": str(old_val), "new": str(new_val)})

    # 状态转换验证
    if "status" in data:
        new_status = data["status"]
        if req.status not in VALID_TRANSITIONS:
            return error(msg=f"当前状态 {req.status} 不允许转换")
        if new_status not in VALID_TRANSITIONS.get(req.status, []):
            return error(msg=f"不允许从 {req.status} 转换到 {new_status}")
        if new_status == "done" and not req.completed_at:
            req.completed_at = datetime.now()

    req.version += 1
    db.session.commit()

    # 记录活动日志
    if changes:
        _log_activity(req.id, user_id, "update", json.dumps(changes), None, None)

    return success(msg="更新成功")


@requirement_bp.route("/<int:req_id>", methods=["DELETE"])
@jwt_required()
def delete_requirement(req_id):
    """软删除需求"""
    req = Requirement.query.get(req_id)
    if not req:
        return error(msg="需求不存在")
    req.deleted_at = datetime.now()
    db.session.commit()
    return success(msg="删除成功")


# ==================== 状态转换 ====================

@requirement_bp.route("/<int:req_id>/transition", methods=["POST"])
@jwt_required()
def transition_requirement(req_id):
    """状态转换（带状态机校验）"""
    data = request.get_json()
    new_status = data.get("status") if data else None
    if not new_status:
        return error(msg="目标状态不能为空")

    req = Requirement.query.get(req_id)
    if not req:
        return error(msg="需求不存在")

    if req.status not in VALID_TRANSITIONS:
        return error(msg=f"当前状态 {req.status} 不允许转换")
    if new_status not in VALID_TRANSITIONS[req.status]:
        return error(msg=f"不允许从 {req.status} 转换到 {new_status}")

    old_status = req.status
    req.status = new_status
    if new_status == "done":
        req.completed_at = datetime.now()
    req.version += 1
    db.session.commit()

    user_id = _get_current_user_id()
    _log_activity(req.id, user_id, "status_change", "status", old_status, new_status)

    return success(msg=f"状态已更新: {old_status} → {new_status}")


# ==================== 看板数据 ====================

@requirement_bp.route("/kanban", methods=["GET"])
@jwt_required()
def get_kanban():
    """看板数据（按状态分组）"""
    project_id = request.args.get("projectId", type=int)
    q = Requirement.query.filter_by(deleted_at=None, parent_id=None)
    if project_id:
        q = q.filter_by(project_id=project_id)

    # 按状态分类分组
    kanban = {}
    for category, statuses in STATUS_CATEGORIES.items():
        items = q.filter(Requirement.status.in_(statuses)).order_by(Requirement.view_order.asc()).all()
        kanban[category] = [{
            "id": r.id, "title": r.title, "priority": r.priority,
            "status": r.status, "assignee": r.assignee, "tags": r.tags or [],
        } for r in items]

    return success(data=kanban)


# ==================== 里程碑 ====================

@requirement_bp.route("/milestones", methods=["GET"])
@jwt_required()
def list_milestones():
    """里程碑列表"""
    project_id = request.args.get("projectId", type=int)
    q = Milestone.query
    if project_id:
        q = q.filter_by(project_id=project_id)
    milestones = q.order_by(Milestone.due_date.asc()).all()
    return success(data=[{
        "id": m.id, "projectId": m.project_id, "title": m.title,
        "description": m.description, "dueDate": m.due_date.isoformat() if m.due_date else None,
        "status": m.status,
    } for m in milestones])


@requirement_bp.route("/milestones", methods=["POST"])
@jwt_required()
def create_milestone():
    """创建里程碑"""
    data = request.get_json()
    if not data or not data.get("title") or not data.get("projectId"):
        return error(msg="标题和项目不能为空")
    ms = Milestone(
        project_id=data["projectId"], title=data["title"],
        description=data.get("description", ""),
        due_date=datetime.strptime(data["dueDate"], "%Y-%m-%d").date() if data.get("dueDate") else None,
    )
    db.session.add(ms)
    db.session.commit()
    return success(data={"id": ms.id}, msg="创建成功")


# ==================== 活动日志 ====================

def _log_activity(req_id, user_id, action, field_name=None, old_value=None, new_value=None):
    """记录活动日志"""
    activity = RequirementActivity(
        requirement_id=req_id, user_id=user_id, action=action,
        field_name=field_name, old_value=old_value, new_value=new_value,
    )
    db.session.add(activity)


# ==================== 日历视图 ====================

@requirement_bp.route("/calendar", methods=["GET"])
@jwt_required()
def get_calendar():
    """日历数据（按日期分组返回需求）"""
    project_id = request.args.get("projectId", type=int)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not year or not month:
        now = datetime.now()
        year = now.year
        month = now.month

    # 计算该月的起止日期
    from datetime import date
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    q = Requirement.query.filter(
        Requirement.deleted_at.is_(None),
        Requirement.due_date >= start_date,
        Requirement.due_date < end_date,
    )
    if project_id:
        q = q.filter_by(project_id=project_id)

    requirements = q.all()

    # 按日期分组
    events = {}
    for r in requirements:
        date_key = r.due_date.strftime("%Y-%m-%d")
        if date_key not in events:
            events[date_key] = []
        events[date_key].append({
            "id": r.id,
            "title": r.title,
            "priority": r.priority,
            "status": r.status,
            "assignee": r.assignee,
            "dueDate": r.due_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return success(data={"events": events, "year": year, "month": month})


# ==================== 需求日历 ====================

@requirement_bp.route("/calendar/requirements", methods=["GET"])
@jwt_required()
def get_requirement_calendar():
    """需求日历（按日期分组返回需求，每个需求包含关联的提交）"""
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    project_id = request.args.get("projectId", type=int)

    if not year or not month:
        now = datetime.now()
        year = now.year
        month = now.month

    from datetime import date as date_type
    start_date = date_type(year, month, 1)
    if month == 12:
        end_date = date_type(year + 1, 1, 1)
    else:
        end_date = date_type(year, month + 1, 1)

    # 查询该月有提交关联的需求
    commits_in_month = RequirementCommit.query.filter(
        RequirementCommit.commit_date >= start_date,
        RequirementCommit.commit_date < end_date,
    ).all()

    # 按需求分组
    req_map = {}
    for rc in commits_in_month:
        if rc.requirement_id not in req_map:
            req_map[rc.requirement_id] = {"requirement": None, "commits": []}
        req_map[rc.requirement_id]["commits"].append(rc)

    # 批量加载需求
    req_ids = list(req_map.keys())
    requirements = Requirement.query.filter(Requirement.id.in_(req_ids), Requirement.deleted_at.is_(None)).all()
    req_dict = {r.id: r for r in requirements}

    # 按日期分组
    events = {}
    for req_id, data in req_map.items():
        req = req_dict.get(req_id)
        if not req:
            continue

        # 该需求在该月的提交日期
        commit_dates = set()
        for rc in data["commits"]:
            if rc.commit_date:
                commit_dates.add(rc.commit_date)

        # 需求在日历上的展示日期 = 最早提交日期
        display_date = min(commit_dates) if commit_dates else start_date
        date_key = display_date.strftime("%Y-%m-%d")

        if date_key not in events:
            events[date_key] = []

        # 按模块分组提交
        commits_by_module = {}
        for rc in data["commits"]:
            mod = rc.repo_module
            if mod not in commits_by_module:
                commits_by_module[mod] = []
            commits_by_module[mod].append({
                "hash": rc.commit_hash[:7],
                "fullHash": rc.commit_hash,
                "subject": rc.commit_subject,
                "author": rc.commit_author,
                "date": rc.commit_date.strftime("%Y-%m-%d") if rc.commit_date else None,
                "files": rc.files_changed or [],
            })

        events[date_key].append({
            "id": req.id,
            "title": req.title,
            "projectId": req.project_id,
            "status": req.status,
            "priority": req.priority,
            "requirementType": req.requirement_type,
            "commits": commits_by_module,
            "totalCommits": len(data["commits"]),
        })

    return success(data={
        "events": events,
        "year": year,
        "month": month,
        "total": len(req_map),
    })


# ==================== 标签管理 ====================

@requirement_bp.route("/tags", methods=["GET"])
@jwt_required()
def list_tags():
    """获取所有标签"""
    tags = RequirementLabel.query.order_by(RequirementLabel.created_at.desc()).all()
    return success(data=[{
        "id": t.id, "name": t.name, "color": t.color,
        "createdAt": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    } for t in tags])


@requirement_bp.route("/tags", methods=["POST"])
@jwt_required()
def create_tag():
    """创建标签"""
    data = request.get_json()
    if not data or not data.get("name"):
        return error(msg="标签名不能为空")
    tag = RequirementLabel(name=data["name"], color=data.get("color", "#409eff"))
    db.session.add(tag)
    db.session.commit()
    return success(data={"id": tag.id}, msg="创建成功")


@requirement_bp.route("/tags/<int:tag_id>", methods=["PUT"])
@jwt_required()
def update_tag(tag_id):
    """更新标签"""
    tag = RequirementLabel.query.get(tag_id)
    if not tag:
        return error(msg="标签不存在")
    data = request.get_json()
    if "name" in data:
        tag.name = data["name"]
    if "color" in data:
        tag.color = data["color"]
    db.session.commit()
    return success(msg="更新成功")


@requirement_bp.route("/tags/<int:tag_id>", methods=["DELETE"])
@jwt_required()
def delete_tag(tag_id):
    """删除标签"""
    tag = RequirementLabel.query.get(tag_id)
    if not tag:
        return error(msg="标签不存在")
    RequirementLabelMap.query.filter_by(label_id=tag_id).delete()
    db.session.delete(tag)
    db.session.commit()
    return success(msg="删除成功")


@requirement_bp.route("/tags/<int:req_id>", methods=["POST"])
@jwt_required()
def add_tag_to_requirement(req_id):
    """给需求添加标签"""
    data = request.get_json()
    tag_id = data.get("tag_id")
    if not tag_id:
        return error(msg="标签ID不能为空")
    existing = RequirementLabelMap.query.filter_by(requirement_id=req_id, label_id=tag_id).first()
    if existing:
        return success(msg="标签已存在")
    link = RequirementLabelMap(requirement_id=req_id, label_id=tag_id)
    db.session.add(link)
    db.session.commit()
    return success(msg="添加成功")


@requirement_bp.route("/tags/<int:req_id>", methods=["GET"])
@jwt_required()
def get_requirement_tags(req_id):
    """获取需求的标签"""
    links = RequirementLabelMap.query.filter_by(requirement_id=req_id).all()
    tag_ids = [l.label_id for l in links]
    tags = RequirementLabel.query.filter(RequirementLabel.id.in_(tag_ids)).all()
    return success(data=[{
        "id": t.id, "name": t.name, "color": t.color,
    } for t in tags])


@requirement_bp.route("/tags/<int:req_id>/<int:tag_id>", methods=["DELETE"])
@jwt_required()
def remove_tag_from_requirement(req_id, tag_id):
    """移除需求的标签"""
    RequirementLabelMap.query.filter_by(requirement_id=req_id, label_id=tag_id).delete()
    db.session.commit()
    return success(msg="移除成功")


# ==================== 附件管理 ====================

@requirement_bp.route("/attachments/<int:req_id>", methods=["GET"])
@jwt_required()
def list_attachments(req_id):
    """获取需求的附件列表"""
    attachments = RequirementAttachment.query.filter_by(requirement_id=req_id).order_by(
        RequirementAttachment.created_at.desc()
    ).all()
    return success(data=[{
        "id": a.id, "fileName": a.file_name, "filePath": a.file_path,
        "fileSize": a.file_size, "fileType": a.file_type,
        "uploadedBy": a.uploaded_by, "createdAt": a.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "url": f"/api/v1/requirements/attachments/{a.id}/download",
    } for a in attachments])


# ==================== 评论管理 ====================

@requirement_bp.route("/comments/<int:req_id>", methods=["GET"])
@jwt_required()
def list_comments(req_id):
    """获取需求的评论列表"""
    comments = RequirementComment.query.filter_by(requirement_id=req_id).order_by(
        RequirementComment.created_at.asc()
    ).all()
    return success(data=[{
        "id": c.id, "content": c.content,
        "createdBy": c.created_by, "createdAt": c.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    } for c in comments])


@requirement_bp.route("/<int:req_id>/commits", methods=["GET"])
@jwt_required()
def get_requirement_commits(req_id):
    """获取需求关联的提交记录"""
    req = Requirement.query.get(req_id)
    if not req:
        return error(msg="需求不存在")

    commits = RequirementCommit.query.filter_by(requirement_id=req_id).order_by(
        RequirementCommit.commit_date.desc()
    ).all()

    result = []
    for rc in commits:
        result.append({
            "id": rc.id,
            "module": rc.repo_module,
            "hash": rc.commit_hash[:7],
            "fullHash": rc.commit_hash,
            "subject": rc.commit_subject,
            "author": rc.commit_author,
            "date": rc.commit_date.strftime("%Y-%m-%d") if rc.commit_date else None,
            "files": rc.files_changed or [],
        })

    return success(data=result)


# ==================== 统计视图 ====================

@requirement_bp.route("/statistics", methods=["GET"])
@jwt_required()
def get_statistics():
    """统计数据"""
    project_id = request.args.get("projectId", type=int)

    q = Requirement.query.filter_by(deleted_at=None)
    if project_id:
        q = q.filter_by(project_id=project_id)

    all_reqs = q.all()
    total = len(all_reqs)

    # 状态分布
    status_stats = {}
    for r in all_reqs:
        status_stats[r.status] = status_stats.get(r.status, 0) + 1

    # 优先级分布
    priority_stats = {}
    for r in all_reqs:
        priority_stats[r.priority] = priority_stats.get(r.priority, 0) + 1

    # 负责人工作量
    assignee_stats = {}
    for r in all_reqs:
        assignee = r.assignee or "未分配"
        if assignee not in assignee_stats:
            assignee_stats[assignee] = {"total": 0, "completed": 0}
        assignee_stats[assignee]["total"] += 1
        if r.status == "done":
            assignee_stats[assignee]["completed"] += 1

    # 近 30 天完成趋势
    from datetime import timedelta
    today = datetime.now().date()
    trend = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        completed = sum(
            1 for r in all_reqs
            if r.status == "done" and r.completed_at and r.completed_at.date() == day
        )
        trend.append({"date": day.strftime("%Y-%m-%d"), "completed": completed})

    return success(data={
        "total": total,
        "statusStats": status_stats,
        "priorityStats": priority_stats,
        "assigneeStats": assignee_stats,
        "trend": trend,
    })
