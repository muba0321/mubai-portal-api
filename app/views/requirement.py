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
from app.models.requirement import Project, Requirement, Milestone
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
    projects = q.order_by(Project.created_at.desc()).all()
    return success(data=[{
        "id": p.id, "name": p.name, "description": p.description,
        "status": p.status, "createdAt": p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
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


@requirement_bp.route("/<int:req_id>", methods=["PUT"])
@jwt_required()
def update_requirement(req_id):
    """更新需求"""
    req = Requirement.query.get(req_id)
    if not req:
        return error(msg="需求不存在")

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
