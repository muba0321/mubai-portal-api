"""权限装饰器和权限查询工具"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.models.sys_user import SysUser
from app.models.sys_role import Role
from app.models.sys_user_role import UserRole
from app.models.sys_role_menu import RoleMenu
from app.models.sys_menu import Menu
from app.extensions import db


def get_user_permissions(user_id):
    """获取用户的所有权限标识列表"""
    user = SysUser.query.get(user_id)
    if not user:
        return []

    # 超级管理员拥有通配权限
    if user.is_admin:
        return ["*:*:*"]

    # 获取用户所有角色的权限
    role_ids = db.session.query(UserRole.role_id).filter_by(user_id=user_id).all()
    role_ids = [r[0] for r in role_ids]

    if not role_ids:
        return []

    # 获取这些角色关联的所有菜单权限标识
    menu_codes = (
        db.session.query(Menu.code)
        .join(RoleMenu, RoleMenu.menu_id == Menu.id)
        .filter(RoleMenu.role_id.in_(role_ids))
        .filter(Menu.code != "")
        .filter(Menu.status == 1)
        .distinct()
        .all()
    )
    return [m[0] for m in menu_codes if m[0]]


def get_user_roles(user_id):
    """获取用户的角色编码列表"""
    user = SysUser.query.get(user_id)
    if not user:
        return []

    if user.is_admin:
        return ["ROOT"]

    role_ids = db.session.query(UserRole.role_id).filter_by(user_id=user_id).all()
    role_ids = [r[0] for r in role_ids]

    if not role_ids:
        return []

    roles = Role.query.filter(Role.id.in_(role_ids), Role.status == 1).all()
    return [r.code for r in roles]


def get_user_menu_tree(user_id):
    """获取用户有权访问的菜单树"""
    user = SysUser.query.get(user_id)
    if not user:
        return []

    if user.is_admin:
        # 管理员返回全部目录和菜单
        menus = Menu.query.filter(
            Menu.type.in_(["C", "M"]),
            Menu.status == 1,
            Menu.visible == 1,
        ).order_by(Menu.sort).all()
        return _build_menu_tree(menus, 0)

    role_ids = db.session.query(UserRole.role_id).filter_by(user_id=user_id).all()
    role_ids = [r[0] for r in role_ids]

    if not role_ids:
        return []

    menu_ids = (
        db.session.query(RoleMenu.menu_id)
        .filter(RoleMenu.role_id.in_(role_ids))
        .distinct()
        .all()
    )
    menu_ids = [m[0] for m in menu_ids]

    menus = (
        Menu.query.filter(
            Menu.id.in_(menu_ids),
            Menu.type.in_(["C", "M"]),
            Menu.status == 1,
        )
        .order_by(Menu.sort)
        .all()
    )
    return _build_menu_tree(menus, 0)


def _build_menu_tree(menus, parent_id):
    """递归构建菜单树"""
    result = []
    for m in menus:
        if m.parent_id == parent_id:
            item = {
                "id": str(m.id),
                "parentId": str(m.parent_id),
                "name": m.name,
                "type": m.type,
                "path": m.path or "",
                "component": m.component or "",
                "icon": m.icon or "",
                "sort": m.sort,
                "visible": m.visible,
                "redirect": m.redirect or "",
                "alwaysShow": m.always_show,
                "keepAlive": m.keep_alive,
                "perm": m.code or "",
                "children": _build_menu_tree(menus, m.id),
            }
            result.append(item)
    return result


def require_permission(code: str):
    """权限装饰器: 检查当前用户是否拥有指定权限"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_id = get_jwt_identity()
            if isinstance(user_id, str):
                user_id = int(user_id)

            user = SysUser.query.get(user_id)
            if not user:
                return jsonify({"code": "A0230", "msg": "用户不存在", "data": None}), 401

            # 超级管理员跳过所有权限检查
            if user.is_admin:
                return f(*args, **kwargs)

            perms = get_user_permissions(user_id)
            if code not in perms:
                return jsonify({"code": "A0301", "msg": "权限不足", "data": None}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def success_response(data=None, msg="success"):
    """统一成功响应"""
    return jsonify({"code": "00000", "data": data, "msg": msg}), 200


def error_response(msg="操作失败", code="500"):
    """统一错误响应"""
    return jsonify({"code": code, "data": None, "msg": msg}), 400
