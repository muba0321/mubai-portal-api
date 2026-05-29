from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.sys_role import Role
from app.models.sys_role_menu import RoleMenu
from app.models.sys_menu import Menu
from app.utils.permission import require_permission, success_response, error_response

sys_role_bp = Blueprint("sys_role", __name__)


DATA_SCOPE_MAP = {
    1: "all",
    2: "dept_and_child",
    3: "dept",
    4: "self",
    5: "custom",
}
DATA_SCOPE_LABEL_MAP = {v: k for k, v in DATA_SCOPE_MAP.items()}


def role_to_dict(r):
    return {
        "id": str(r.id),
        "name": r.name,
        "code": r.code,
        "sort": r.sort,
        "dataScope": DATA_SCOPE_LABEL_MAP.get(r.data_scope, 1),
        "dataScopeLabel": {"all": "全部数据", "dept_and_child": "本部门及以下", "dept": "本部门", "self": "仅本人", "custom": "自定义"}.get(r.data_scope, ""),
        "status": r.status,
        "remark": r.remark or "",
        "updateTime": r.updated_at.isoformat() if r.updated_at else None,
    }


def role_to_form_dict(r):
    d = {
        "id": str(r.id),
        "name": r.name,
        "code": r.code,
        "sort": r.sort,
        "dataScope": DATA_SCOPE_LABEL_MAP.get(r.data_scope, 1),
        "status": r.status,
        "remark": r.remark or "",
    }
    if r.data_scope == "custom":
        dept_ids = db.session.query(RoleMenu.menu_id).filter_by(role_id=r.id).all()
        d["deptIds"] = [str(x[0]) for x in dept_ids]
    return d


@sys_role_bp.route("", methods=["GET"])
@jwt_required()
@require_permission("sys:role:list")
def list_roles():
    keywords = request.args.get("keywords", "")
    page_num = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 10, type=int)

    query = Role.query.filter_by(status=1)
    if keywords:
        query = query.filter(Role.name.contains(keywords))

    total = query.count()
    roles = query.order_by(Role.sort).offset((page_num - 1) * page_size).limit(page_size).all()
    return success_response({"list": [role_to_dict(r) for r in roles], "total": total})


@sys_role_bp.route("/options", methods=["GET"])
@jwt_required()
def role_options():
    roles = Role.query.filter_by(status=1).order_by(Role.sort).all()
    return success_response([{"value": r.id, "label": r.name} for r in roles])


@sys_role_bp.route("/<int:role_id>/form", methods=["GET"])
@jwt_required()
@require_permission("sys:role:list")
def get_role_form(role_id):
    role = Role.query.get_or_404(role_id)
    return success_response(role_to_form_dict(role))


@sys_role_bp.route("/<int:role_id>/menu-ids", methods=["GET"])
@jwt_required()
def get_role_menus(role_id):
    Role.query.get_or_404(role_id)
    menu_ids = db.session.query(RoleMenu.menu_id).filter_by(role_id=role_id).all()
    return success_response([str(m[0]) for m in menu_ids])


@sys_role_bp.route("/<int:role_id>/menus", methods=["PUT"])
@jwt_required()
@require_permission("sys:role:assign")
def update_role_menus(role_id):
    Role.query.get_or_404(role_id)
    data = request.get_json()
    RoleMenu.query.filter_by(role_id=role_id).delete()
    for mid in data.get("menuIds", []):
        db.session.add(RoleMenu(role_id=role_id, menu_id=int(mid)))
    db.session.commit()
    return success_response(msg="权限分配成功")


@sys_role_bp.route("/<int:role_id>/dept-ids", methods=["GET"])
@jwt_required()
def get_role_depts(role_id):
    Role.query.get_or_404(role_id)
    # 简化: 复用 menu_ids 存储自定义数据权限
    menu_ids = db.session.query(RoleMenu.menu_id).filter_by(role_id=role_id).all()
    return success_response([str(m[0]) for m in menu_ids])


@sys_role_bp.route("", methods=["POST"])
@jwt_required()
@require_permission("sys:role:create")
def create_role():
    data = request.get_json()
    if Role.query.filter_by(code=data["code"]).first():
        return error_response("角色编码已存在", "400")

    ds_num = data.get("dataScope", 4)
    data_scope = DATA_SCOPE_MAP.get(ds_num, "self")

    role = Role(
        name=data["name"],
        code=data["code"],
        sort=data.get("sort", 0),
        data_scope=data_scope,
        status=data.get("status", 1),
        remark=data.get("remark", ""),
    )
    db.session.add(role)
    db.session.commit()
    return success_response(role_to_dict(role), "新增成功")


@sys_role_bp.route("/<int:role_id>", methods=["PUT"])
@jwt_required()
@require_permission("sys:role:update")
def update_role(role_id):
    role = Role.query.get_or_404(role_id)
    data = request.get_json()
    for key in ["name", "code", "sort", "status", "remark"]:
        if key in data:
            setattr(role, key, data[key])
    if "dataScope" in data:
        role.data_scope = DATA_SCOPE_MAP.get(data["dataScope"], "self")
    db.session.commit()
    return success_response(role_to_dict(role), "更新成功")


@sys_role_bp.route("/<ids>", methods=["DELETE"])
@jwt_required()
@require_permission("sys:role:delete")
def delete_roles(ids):
    role_ids = [int(x) for x in ids.split(",") if x]
    Role.query.filter(Role.id.in_(role_ids)).delete(synchronize_session=False)
    RoleMenu.query.filter(RoleMenu.role_id.in_(role_ids)).delete(synchronize_session=False)
    db.session.commit()
    return success_response(msg="删除成功")
