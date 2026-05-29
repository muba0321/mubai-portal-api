from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.sys_user import SysUser
from app.models.sys_role import Role
from app.models.sys_user_role import UserRole
from app.models.dept import Dept
from app.utils.permission import require_permission, get_user_permissions, get_user_roles, success_response, error_response

sys_user_bp = Blueprint("sys_user", __name__)


def user_to_dict(u):
    d = {
        "id": str(u.id),
        "username": u.username,
        "nickname": u.nickname or "",
        "email": u.email or "",
        "phone": u.phone or "",
        "gender": u.gender,
        "avatar": u.avatar or "",
        "deptId": str(u.dept_id) if u.dept_id else None,
        "deptName": u.dept.name if u.dept else "",
        "identity": u.identity,
        "status": u.status,
        "isAdmin": u.is_admin,
        "loginIp": u.login_ip or "",
        "loginDate": u.login_date.isoformat() if u.login_date else None,
        "createdAt": u.created_at.isoformat() if u.created_at else None,
    }
    role_ids = db.session.query(UserRole.role_id).filter_by(user_id=u.id).all()
    role_ids = [r[0] for r in role_ids]
    roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []
    d["roleIds"] = [r.id for r in roles]
    d["roleNames"] = ",".join([r.name for r in roles])
    return d


def user_to_form_dict(u):
    d = {
        "id": str(u.id),
        "username": u.username,
        "nickname": u.nickname or "",
        "email": u.email or "",
        "phone": u.phone or "",
        "gender": u.gender,
        "avatar": u.avatar or "",
        "deptId": str(u.dept_id) if u.dept_id else None,
        "status": u.status,
    }
    role_ids = db.session.query(UserRole.role_id).filter_by(user_id=u.id).all()
    d["roleIds"] = [r[0] for r in role_ids]
    return d


@sys_user_bp.route("", methods=["GET"])
@jwt_required()
@require_permission("sys:user:list")
def list_users():
    """用户列表（分页 + 筛选）"""
    keywords = request.args.get("keywords", "")
    status = request.args.get("status")
    dept_id = request.args.get("deptId")
    page_num = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 10, type=int)
    create_time = request.args.get("createTime")  # "2026-01-01,2026-12-31"

    query = SysUser.query.filter_by(deleted=0)
    if keywords:
        query = query.filter(
            SysUser.username.contains(keywords) |
            SysUser.nickname.contains(keywords) |
            (SysUser.phone.isnot(None) & SysUser.phone.contains(keywords))
        )
    if status is not None:
        query = query.filter_by(status=int(status))
    if dept_id:
        query = query.filter_by(dept_id=int(dept_id))
    if create_time:
        dates = create_time.split(",")
        if len(dates) == 2:
            query = query.filter(SysUser.created_at >= dates[0], SysUser.created_at <= dates[1] + " 23:59:59")

    total = query.count()
    users = query.order_by(SysUser.id).offset((page_num - 1) * page_size).limit(page_size).all()
    return success_response({"list": [user_to_dict(u) for u in users], "total": total})


@sys_user_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    user = SysUser.query.get(user_id)
    if not user:
        return error_response("用户不存在", "404"), 404
    return success_response(user_to_dict(user))


@sys_user_bp.route("/<int:user_id>", methods=["GET"])
@jwt_required()
@require_permission("sys:user:list")
def get_user(user_id):
    user = SysUser.query.get_or_404(user_id)
    return success_response(user_to_dict(user))


@sys_user_bp.route("/<int:user_id>/form", methods=["GET"])
@jwt_required()
@require_permission("sys:user:list")
def get_user_form(user_id):
    user = SysUser.query.get_or_404(user_id)
    return success_response(user_to_form_dict(user))


@sys_user_bp.route("/options", methods=["GET"])
@jwt_required()
def get_user_options():
    """用户下拉选项"""
    users = SysUser.query.filter_by(deleted=0, status=1).order_by(SysUser.username).all()
    return success_response([{"value": str(u.id), "label": u.username} for u in users])


@sys_user_bp.route("", methods=["POST"])
@jwt_required()
@require_permission("sys:user:create")
def create_user():
    data = request.get_json()
    if SysUser.query.filter_by(username=data["username"]).first():
        return error_response("用户名已存在", "400")

    from werkzeug.security import generate_password_hash
    user = SysUser(
        username=data["username"],
        password_hash=generate_password_hash(data.get("password", "123456")),
        nickname=data.get("nickname", data["username"]),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        gender=data.get("gender", 0),
        dept_id=int(data["deptId"]) if data.get("deptId") else None,
        status=data.get("status", 1),
    )
    db.session.add(user)
    db.session.flush()

    # 分配角色
    role_ids = data.get("roleIds", [])
    for rid in role_ids:
        db.session.add(UserRole(user_id=user.id, role_id=int(rid)))

    db.session.commit()
    return success_response(user_to_dict(user), "新增成功")


@sys_user_bp.route("/<int:user_id>", methods=["PUT"])
@jwt_required()
@require_permission("sys:user:update")
def update_user(user_id):
    user = SysUser.query.get_or_404(user_id)
    data = request.get_json()

    for key in ["nickname", "email", "phone", "gender", "status", "avatar"]:
        if key in data:
            setattr(user, key, data[key])

    if "deptId" in data:
        user.dept_id = int(data["deptId"]) if data["deptId"] else None

    if data.get("password"):
        from werkzeug.security import generate_password_hash
        user.password_hash = generate_password_hash(data["password"])

    # 更新角色
    if "roleIds" in data:
        UserRole.query.filter_by(user_id=user_id).delete()
        for rid in data["roleIds"]:
            db.session.add(UserRole(user_id=user_id, role_id=int(rid)))

    db.session.commit()
    return success_response(user_to_dict(user), "更新成功")


@sys_user_bp.route("/<int:user_id>", methods=["DELETE"])
@jwt_required()
@require_permission("sys:user:delete")
def delete_user(user_id):
    user = SysUser.query.get_or_404(user_id)
    if user.is_admin:
        return error_response("不能删除管理员账号", "400")
    # 逻辑删除
    user.deleted = 1
    db.session.commit()
    return success_response(msg="删除成功")


@sys_user_bp.route("/<ids>", methods=["DELETE"])
@jwt_required()
@require_permission("sys:user:delete")
def batch_delete_users(ids):
    """批量删除（逗号分隔）"""
    user_ids = [int(x) for x in ids.split(",") if x]
    SysUser.query.filter(SysUser.id.in_(user_ids)).update({"deleted": 1}, synchronize_session=False)
    db.session.commit()
    return success_response(msg="批量删除成功")


@sys_user_bp.route("/<int:user_id>/password", methods=["PUT"])
@jwt_required()
@require_permission("sys:user:reset-password")
def reset_password(user_id):
    data = request.get_json()
    new_password = data.get("newPassword", "")
    if len(new_password) < 6:
        return error_response("密码至少6位", "400")

    from werkzeug.security import generate_password_hash
    user = SysUser.query.get_or_404(user_id)
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return success_response(msg="密码重置成功")


@sys_user_bp.route("/<int:user_id>/status", methods=["PUT"])
@jwt_required()
@require_permission("sys:user:update")
def update_user_status(user_id):
    data = request.get_json()
    user = SysUser.query.get_or_404(user_id)
    user.status = int(data.get("status", 1))
    db.session.commit()
    return success_response(user_to_dict(user), "状态更新成功")


@sys_user_bp.route("/<int:user_id>/roles", methods=["PUT"])
@jwt_required()
@require_permission("sys:user:update")
def update_user_roles(user_id):
    data = request.get_json()
    SysUser.query.get_or_404(user_id)
    UserRole.query.filter_by(user_id=user_id).delete()
    for rid in data.get("roleIds", []):
        db.session.add(UserRole(user_id=user_id, role_id=int(rid)))
    db.session.commit()
    return success_response(msg="角色分配成功")


@sys_user_bp.route("/export", methods=["GET"])
@jwt_required()
@require_permission("sys:user:export")
def export_users():
    """导出用户（简化返回 JSON，实际可生成 CSV）"""
    users = SysUser.query.filter_by(deleted=0).all()
    return success_response([user_to_dict(u) for u in users])
