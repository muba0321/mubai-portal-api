from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.sys_menu import Menu
from app.models.sys_user import SysUser
from app.models.sys_user_role import UserRole
from app.models.sys_role_menu import RoleMenu
from app.utils.permission import get_user_permissions, get_user_roles
from app.utils.response import success, error

system_bp = Blueprint("system", __name__)


@system_bp.route("/users/me", methods=["GET"])
@jwt_required()
def get_current_user():
    user_id = int(get_jwt_identity())
    user = SysUser.query.filter_by(id=user_id, deleted=0).first()
    if not user:
        return error(msg="用户不存在", code="40400")

    return success(data={
        "user_id": user.id,
        "username": user.username,
        "nickname": user.nickname or user.username,
        "email": user.email or "",
        "roles": get_user_roles(user.id),
        "perms": get_user_permissions(user.id),
    })


@system_bp.route("/menus/routes", methods=["GET"])
@jwt_required()
def get_menu_routes():
    """返回当前用户的动态路由配置，控制侧边栏菜单"""
    user_id = int(get_jwt_identity())
    user = SysUser.query.filter_by(id=user_id, deleted=0).first()
    if not user:
        return error(msg="用户不存在", code="40400")

    # 获取用户有权访问的菜单
    if user.is_admin == 1:
        menus = Menu.query.filter(
            Menu.type.in_(["C", "M"]),
            Menu.status == 1,
            Menu.visible == 1,
        ).order_by(Menu.sort).all()
    else:
        role_ids = db.session.query(UserRole.role_id).filter_by(user_id=user_id).all()
        role_ids = [r[0] for r in role_ids]
        if not role_ids:
            return success(data=[])
        menu_ids = db.session.query(RoleMenu.menu_id).filter(
            RoleMenu.role_id.in_(role_ids)
        ).distinct().all()
        menu_ids = [m[0] for m in menu_ids]
        menus = Menu.query.filter(
            Menu.id.in_(menu_ids),
            Menu.type.in_(["C", "M"]),
            Menu.status == 1,
        ).order_by(Menu.sort).all()

    return success(data=_build_route_tree(menus, 0))


def _build_route_tree(menus, parent_id):
    """将菜单转换为前端路由格式"""
    result = []
    for m in menus:
        if m.parent_id == parent_id:
            route = {
                "path": m.path or "",
                "component": "Layout" if m.type == "C" else (m.component or ""),
            }
            if m.redirect:
                route["redirect"] = m.redirect
            meta = {"title": m.name, "icon": m.icon or ""}
            if m.keep_alive:
                meta["keepAlive"] = True
            if m.always_show:
                meta["alwaysShow"] = True
            route["meta"] = meta
            children = _build_route_tree(menus, m.id)
            if children:
                route["children"] = children
            result.append(route)
    return result
