from datetime import datetime
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.sys import SysUser
from app.models.config_entry import ConfigEntry
from app.utils.response import success, error, page_result

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


@system_bp.route("/users", methods=["GET"])
@jwt_required()
def list_users():
    """用户列表"""
    page = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 10, type=int)
    keyword = request.args.get("keyword", "").strip()

    query = SysUser.query.filter_by(deleted=0)
    if keyword:
        query = query.filter(SysUser.username.like(f"%{keyword}%"))

    total = query.count()
    users = query.order_by(SysUser.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for u in users:
        items.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "createdAt": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "",
        })

    return success(data=page_result(total, items))


@system_bp.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    """获取用户详情"""
    user = SysUser.query.filter_by(id=user_id, deleted=0).first()
    if not user:
        return error(msg="用户不存在", code="40400")

    return success(data={
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "createdAt": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "",
    })


@system_bp.route("/users", methods=["POST"])
@jwt_required()
def create_user():
    """新增用户"""
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()
    role = data.get("role", "user")

    if not username or not password:
        return error(msg="用户名和密码不能为空", code="40001")

    if len(password) < 6:
        return error(msg="密码至少 6 位", code="40002")

    if SysUser.query.filter_by(username=username, deleted=0).first():
        return error(msg="用户名已存在", code="40003")

    user = SysUser(
        username=username,
        password_hash=generate_password_hash(password),
        email=email,
        role=role,
    )
    db.session.add(user)
    db.session.commit()

    return success(msg="创建成功", data={"id": user.id, "username": user.username, "role": user.role})


@system_bp.route("/users/<int:user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    """更新用户"""
    user = SysUser.query.filter_by(id=user_id, deleted=0).first()
    if not user:
        return error(msg="用户不存在", code="40400")

    data = request.get_json() or {}
    if "email" in data:
        user.email = data["email"]
    if "role" in data:
        user.role = data["role"]
    if "password" in data and data["password"]:
        if len(data["password"]) < 6:
            return error(msg="密码至少 6 位", code="40002")
        user.password_hash = generate_password_hash(data["password"])

    user.updated_at = datetime.now()
    db.session.commit()

    return success(msg="更新成功")


@system_bp.route("/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    """删除用户（软删除）"""
    user = SysUser.query.filter_by(id=user_id, deleted=0).first()
    if not user:
        return error(msg="用户不存在", code="40400")

    if user.username == "mubai":
        return error(msg="不能删除管理员账号", code="40005")

    user.deleted = 1
    db.session.commit()

    return success(msg="删除成功")


@system_bp.route("/users/<int:user_id>/password", methods=["PUT"])
@jwt_required()
def reset_password(user_id):
    """重置密码"""
    user = SysUser.query.filter_by(id=user_id, deleted=0).first()
    if not user:
        return error(msg="用户不存在", code="40400")

    data = request.get_json() or {}
    new_password = data.get("newPassword", "")
    if not new_password or len(new_password) < 6:
        return error(msg="新密码至少 6 位", code="40002")

    user.password_hash = generate_password_hash(new_password)
    user.updated_at = datetime.now()
    db.session.commit()

    return success(msg="密码重置成功")


@system_bp.route("/menus/routes", methods=["GET"])
@jwt_required()
def get_menu_routes():
    """返回动态路由配置，控制侧边栏菜单"""
    settings = {}
    try:
        entries = ConfigEntry.query.filter(
            ConfigEntry.namespace == "feature-toggle"
        ).all()
        for e in entries:
            settings[e.config_key] = e.config_value == "true"
    except Exception:
        pass

    def feature_enabled(key, default=True):
        return settings.get(key, default)

    menus = [
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
    ]

    if feature_enabled("feature_cmdb"):
        menus.append({
            "path": "/cmdb",
            "component": "Layout",
            "redirect": "/cmdb",
            "meta": {"title": "CMDB 管理", "icon": "Monitor"},
            "children": [
                {"path": "cmdb", "component": "cmdb/index",
                 "meta": {"title": "虚拟机管理", "icon": "Monitor"}}
            ],
        })

    if feature_enabled("feature_database"):
        menus.append({
            "path": "/database",
            "component": "Layout",
            "redirect": "/database",
            "meta": {"title": "数据库管理", "icon": "DataBoard"},
            "children": [
                {"path": "database", "component": "database/index",
                 "meta": {"title": "数据库管理", "icon": "DataBoard"}}
            ],
        })

    if feature_enabled("feature_todo"):
        menus.append({
            "path": "/todo",
            "component": "Layout",
            "redirect": "/todo",
            "meta": {"title": "待办管理", "icon": "List"},
            "children": [
                {"path": "todo", "component": "todo/index",
                 "meta": {"title": "待办管理", "icon": "List"}}
            ],
        })

    if feature_enabled("feature_changelog"):
        menus.append({
            "path": "/changelog",
            "component": "Layout",
            "redirect": "/changelog",
            "meta": {"title": "版本记录", "icon": "Stamp"},
            "children": [
                {"path": "changelog", "component": "changelog/index",
                 "meta": {"title": "版本记录", "icon": "Stamp"}}
            ],
        })

    # 系统设置菜单（管理员可见）
    menus.append({
        "path": "/system",
        "component": "Layout",
        "redirect": "/system/users",
        "meta": {"title": "系统管理", "icon": "Setting"},
        "children": [
            {"path": "users", "component": "system/users/index",
             "meta": {"title": "用户管理", "icon": "UserFilled"}},
            {"path": "settings", "component": "setting/index",
             "meta": {"title": "配置管理", "icon": "Tools"}},
        ],
    })

    return success(data=menus)
