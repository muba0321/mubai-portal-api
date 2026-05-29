from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.dept import Dept
from app.utils.permission import require_permission, success_response, error_response

sys_dept_bp = Blueprint("sys_dept", __name__)


def dept_to_dict(d):
    return {
        "id": str(d.id),
        "name": d.name,
        "code": "",
        "parentId": str(d.parent_id),
        "ancestors": d.ancestors or "",
        "leader": d.leader or "",
        "phone": d.phone or "",
        "email": d.email or "",
        "sort": d.sort,
        "status": d.status,
        "createTime": d.created_at.isoformat() if d.created_at else None,
    }


def dept_to_tree_list(depts, parent_id=0):
    """递归构建部门树"""
    result = []
    for d in depts:
        if d.parent_id == parent_id:
            item = dept_to_dict(d)
            children = dept_to_tree_list(depts, d.id)
            if children:
                item["children"] = children
            result.append(item)
    return result


@sys_dept_bp.route("", methods=["GET"])
@jwt_required()
@require_permission("sys:dept:list")
def list_depts():
    keywords = request.args.get("keywords", "")
    status = request.args.get("status")

    query = Dept.query.filter_by(deleted=0)
    if keywords:
        query = query.filter(Dept.name.contains(keywords))
    if status is not None:
        query = query.filter_by(status=int(status))

    depts = query.order_by(Dept.sort).all()
    return success_response(dept_to_tree_list(depts))


@sys_dept_bp.route("/options", methods=["GET"])
@jwt_required()
def dept_options():
    depts = Dept.query.filter_by(deleted=0, status=1).order_by(Dept.sort).all()
    return success_response(_dept_to_options(depts))


def _dept_to_options(depts, parent_id=0):
    result = []
    for d in depts:
        if d.parent_id == parent_id:
            item = {"value": str(d.id), "label": d.name}
            children = _dept_to_options(depts, d.id)
            if children:
                item["children"] = children
            result.append(item)
    return result


@sys_dept_bp.route("/<int:dept_id>/form", methods=["GET"])
@jwt_required()
@require_permission("sys:dept:list")
def get_dept_form(dept_id):
    dept = Dept.query.get_or_404(dept_id)
    return success_response(dept_to_dict(dept))


@sys_dept_bp.route("", methods=["POST"])
@jwt_required()
@require_permission("sys:dept:create")
def create_dept():
    data = request.get_json()
    parent_id = int(data.get("parentId", 0))
    parent = Dept.query.get(parent_id) if parent_id > 0 else None

    ancestors = f"{parent.ancestors},{parent_id}" if parent else "0"

    dept = Dept(
        name=data["name"],
        parent_id=parent_id,
        ancestors=ancestors,
        leader=data.get("leader", ""),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        sort=data.get("sort", 0),
        status=data.get("status", 1),
    )
    db.session.add(dept)
    db.session.commit()
    return success_response(dept_to_dict(dept), "新增成功")


@sys_dept_bp.route("/<int:dept_id>", methods=["PUT"])
@jwt_required()
@require_permission("sys:dept:update")
def update_dept(dept_id):
    dept = Dept.query.get_or_404(dept_id)
    data = request.get_json()
    for key in ["name", "leader", "phone", "email", "sort", "status"]:
        if key in data:
            setattr(dept, key, data[key])
    db.session.commit()
    return success_response(dept_to_dict(dept), "更新成功")


@sys_dept_bp.route("/<ids>", methods=["DELETE"])
@jwt_required()
@require_permission("sys:dept:delete")
def delete_depts(ids):
    dept_ids = [int(x) for x in ids.split(",") if x]
    # 检查是否有子部门
    has_children = Dept.query.filter(
        Dept.parent_id.in_(dept_ids), Dept.deleted == 0
    ).first()
    if has_children:
        return error_response("存在子部门，无法删除", "400")

    Dept.query.filter(Dept.id.in_(dept_ids)).update({"deleted": 1}, synchronize_session=False)
    db.session.commit()
    return success_response(msg="删除成功")
