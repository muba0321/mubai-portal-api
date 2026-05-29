from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.sys_menu import Menu
from app.utils.permission import require_permission, get_user_menu_tree, success_response, error_response

sys_menu_bp = Blueprint("sys_menu", __name__)


def menu_to_dict(m):
    return {
        "id": str(m.id),
        "parentId": str(m.parent_id),
        "name": m.name,
        "type": m.type,
        "path": m.path or "",
        "component": m.component or "",
        "icon": m.icon or "",
        "sort": m.sort,
        "visible": m.visible,
        "status": m.status,
        "perm": m.code or "",
        "redirect": m.redirect or "",
        "alwaysShow": m.always_show,
        "keepAlive": m.keep_alive,
        "createTime": m.created_at.isoformat() if m.created_at else None,
    }


def menu_to_tree_list(menus, parent_id=0):
    result = []
    for m in menus:
        if m.parent_id == parent_id:
            item = menu_to_dict(m)
            children = menu_to_tree_list(menus, m.id)
            if children:
                item["children"] = children
            result.append(item)
    return result


def menu_to_form_dict(m):
    return {
        "id": str(m.id),
        "parentId": str(m.parent_id),
        "name": m.name,
        "type": m.type,
        "path": m.path or "",
        "component": m.component or "",
        "icon": m.icon or "",
        "sort": m.sort,
        "visible": m.visible,
        "perm": m.code or "",
        "redirect": m.redirect or "",
        "alwaysShow": m.always_show,
        "keepAlive": m.keep_alive,
    }


@sys_menu_bp.route("/routes", methods=["GET"])
@jwt_required()
def get_user_routes():
    """当前用户的路由树（用于前端动态路由）"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    tree = get_user_menu_tree(user_id)
    return success_response(tree)


@sys_menu_bp.route("", methods=["GET"])
@jwt_required()
@require_permission("sys:menu:list")
def list_menus():
    keywords = request.args.get("keywords", "")
    query = Menu.query
    if keywords:
        query = query.filter(Menu.name.contains(keywords))
    menus = query.order_by(Menu.sort).all()
    return success_response(menu_to_tree_list(menus))


@sys_menu_bp.route("/options", methods=["GET"])
@jwt_required()
def menu_options():
    only_parent = request.args.get("onlyParent") == "true"
    scope = request.args.get("scope")
    query = Menu.query.filter(Menu.status == 1)
    if only_parent:
        query = query.filter(Menu.type.in_(["C"]))
    if scope:
        query = query.filter(Menu.parent_id == int(scope))
    menus = query.order_by(Menu.sort).all()
    return success_response(_menu_to_options(menus))


def _menu_to_options(menus, parent_id=0):
    result = []
    for m in menus:
        if m.parent_id == parent_id:
            item = {"value": str(m.id), "label": m.name}
            children = _menu_to_options(menus, m.id)
            if children:
                item["children"] = children
            result.append(item)
    return result


@sys_menu_bp.route("/<int:menu_id>/form", methods=["GET"])
@jwt_required()
@require_permission("sys:menu:list")
def get_menu_form(menu_id):
    menu = Menu.query.get_or_404(menu_id)
    return success_response(menu_to_form_dict(menu))


@sys_menu_bp.route("", methods=["POST"])
@jwt_required()
@require_permission("sys:menu:create")
def create_menu():
    data = request.get_json()
    menu = Menu(
        name=data["name"],
        parent_id=int(data.get("parentId", 0)),
        type=data.get("type", "M"),
        path=data.get("path", ""),
        component=data.get("component", ""),
        icon=data.get("icon", ""),
        sort=data.get("sort", 0),
        visible=data.get("visible", 1),
        code=data.get("perm", ""),
        redirect=data.get("redirect", ""),
        always_show=data.get("alwaysShow", 0),
        keep_alive=data.get("keepAlive", 0),
    )
    db.session.add(menu)
    db.session.commit()
    return success_response(menu_to_dict(menu), "新增成功")


@sys_menu_bp.route("/<int:menu_id>", methods=["PUT"])
@jwt_required()
@require_permission("sys:menu:update")
def update_menu(menu_id):
    menu = Menu.query.get_or_404(menu_id)
    data = request.get_json()
    for key in ["name", "type", "path", "component", "icon", "sort", "visible", "redirect", "perm"]:
        if key in data:
            setattr(menu, key, data[key])
    if "alwaysShow" in data:
        menu.always_show = data["alwaysShow"]
    if "keepAlive" in data:
        menu.keep_alive = data["keepAlive"]
    db.session.commit()
    return success_response(menu_to_dict(menu), "更新成功")


@sys_menu_bp.route("/<int:menu_id>", methods=["DELETE"])
@jwt_required()
@require_permission("sys:menu:delete")
def delete_menu(menu_id):
    has_children = Menu.query.filter_by(parent_id=menu_id).first()
    if has_children:
        return error_response("存在子菜单，无法删除", "400")
    menu = Menu.query.get_or_404(menu_id)
    db.session.delete(menu)
    # 清理角色菜单关联
    from app.models.sys_role_menu import RoleMenu
    RoleMenu.query.filter_by(menu_id=menu_id).delete()
    db.session.commit()
    return success_response(msg="删除成功")
