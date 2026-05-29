from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.todo import Project, TodoItem
from app.utils.response import success, error

todo_bp = Blueprint("todo", __name__)


def project_to_dict(p):
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "status": p.status,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def todo_to_dict(t, include_children=True):
    result = {
        "id": t.id,
        "project_id": t.project_id,
        "parent_id": t.parent_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "assignee": t.assignee,
        "due_date": t.due_date,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }
    if include_children and t.children:
        result["children"] = [todo_to_dict(c, include_children=True) for c in t.children]
    return result


# ==================== Project Endpoints ====================

@todo_bp.route("/projects", methods=["GET"])
@jwt_required()
def list_projects():
    status = request.args.get("status")
    q = Project.query
    if status:
        q = q.filter_by(status=status)
    projects = q.order_by(Project.created_at.desc()).all()
    return success(data=[project_to_dict(p) for p in projects])


@todo_bp.route("/projects", methods=["POST"])
@jwt_required()
def create_project():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return error(msg="项目名称不能为空")
    if Project.query.filter_by(name=name).first():
        return error(msg="项目名称已存在")

    project = Project(
        name=name,
        description=data.get("description", ""),
        status=data.get("status", "active"),
    )
    db.session.add(project)
    db.session.commit()
    return success(msg="新增成功", data=project_to_dict(project))


@todo_bp.route("/projects/<int:project_id>", methods=["PUT"])
@jwt_required()
def update_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return error(msg="项目不存在")

    data = request.get_json() or {}
    if "name" in data:
        name = data["name"].strip()
        if not name:
            return error(msg="项目名称不能为空")
        existing = Project.query.filter_by(name=name).first()
        if existing and existing.id != project_id:
            return error(msg="项目名称已存在")
        project.name = name
    if "description" in data:
        project.description = data["description"]
    if "status" in data:
        project.status = data["status"]

    db.session.commit()
    return success(msg="修改成功", data=project_to_dict(project))


@todo_bp.route("/projects/<int:project_id>", methods=["DELETE"])
@jwt_required()
def delete_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return error(msg="项目不存在")

    db.session.delete(project)
    db.session.commit()
    return success(msg="删除成功")


# ==================== Todo Endpoints ====================

@todo_bp.route("/projects/<int:project_id>/todos", methods=["GET"])
@jwt_required()
def get_project_todos(project_id):
    project = Project.query.get(project_id)
    if not project:
        return error(msg="项目不存在")

    todos = TodoItem.query.filter_by(
        project_id=project_id, parent_id=None
    ).order_by(TodoItem.created_at.desc()).all()

    return success(data=[todo_to_dict(t) for t in todos])


@todo_bp.route("/todos", methods=["GET"])
@jwt_required()
def list_todos():
    project_id = request.args.get("projectId", type=int)
    status = request.args.get("status")
    priority = request.args.get("priority")

    q = TodoItem.query.filter_by(parent_id=None)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    if priority:
        q = q.filter_by(priority=priority)

    todos = q.order_by(TodoItem.created_at.desc()).all()
    return success(data=[todo_to_dict(t) for t in todos])


@todo_bp.route("/todos", methods=["POST"])
@jwt_required()
def create_todo():
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    project_id = data.get("projectId")

    if not title:
        return error(msg="标题不能为空")
    if not project_id:
        return error(msg="所属项目不能为空")

    project = Project.query.get(project_id)
    if not project:
        return error(msg="所属项目不存在")

    parent_id = data.get("parentId")
    if parent_id:
        parent = TodoItem.query.get(parent_id)
        if not parent or parent.project_id != project_id:
            return error(msg="无效的父待办项")

    todo = TodoItem(
        project_id=project_id,
        parent_id=parent_id,
        title=title,
        description=data.get("description", ""),
        status=data.get("status", "pending"),
        priority=data.get("priority", "medium"),
        assignee=data.get("assignee", ""),
        due_date=data.get("dueDate"),
    )
    db.session.add(todo)
    db.session.commit()
    return success(msg="新增成功", data=todo_to_dict(todo))


@todo_bp.route("/todos/<int:todo_id>", methods=["PUT"])
@jwt_required()
def update_todo(todo_id):
    todo = TodoItem.query.get(todo_id)
    if not todo:
        return error(msg="待办项不存在")

    data = request.get_json() or {}
    if "title" in data:
        title = data["title"].strip()
        if not title:
            return error(msg="标题不能为空")
        todo.title = title
    if "description" in data:
        todo.description = data["description"]
    if "status" in data:
        todo.status = data["status"]
    if "priority" in data:
        todo.priority = data["priority"]
    if "assignee" in data:
        todo.assignee = data["assignee"]
    if "dueDate" in data:
        todo.due_date = data["dueDate"]
    if "parentId" in data:
        new_parent_id = data["parentId"]
        if new_parent_id:
            parent = TodoItem.query.get(new_parent_id)
            if not parent or parent.project_id != todo.project_id:
                return error(msg="无效的父待办项")
        todo.parent_id = new_parent_id

    db.session.commit()
    return success(msg="修改成功", data=todo_to_dict(todo))


@todo_bp.route("/todos/<int:todo_id>", methods=["DELETE"])
@jwt_required()
def delete_todo(todo_id):
    todo = TodoItem.query.get(todo_id)
    if not todo:
        return error(msg="待办项不存在")

    db.session.delete(todo)
    db.session.commit()
    return success(msg="删除成功")
