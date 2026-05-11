from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.sys import SysUser
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
        "email": user.email,
        "role": user.role,
    })


@system_bp.route("/menus/routes", methods=["GET"])
@jwt_required()
def get_menu_routes():
    """返回动态路由配置，控制侧边栏菜单"""
    return success(data=[
        {
            "path": "/dashboard",
            "component": "Layout",
            "redirect": "/dashboard",
            "meta": {"title": "首页", "icon": "HomeFilled"},
            "children": [
                {"path": "dashboard", "component": "dashboard/index",
                 "meta": {"title": "首页", "icon": "HomeFilled"}}
            ],
        },
        {
            "path": "/cmdb",
            "component": "Layout",
            "redirect": "/cmdb",
            "meta": {"title": "CMDB 管理", "icon": "Monitor"},
            "children": [
                {"path": "cmdb", "component": "cmdb/index",
                 "meta": {"title": "虚拟机管理", "icon": "Monitor"}}
            ],
        },
    ])
