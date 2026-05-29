from flask import Blueprint, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.models.sys_user import SysUser
from app.utils.permission import get_user_permissions, get_user_roles
from app.utils.response import success, error

auth_bp = Blueprint("auth", __name__)


def _build_user_info(user):
    """构建用户信息返回"""
    return {
        "userId": str(user.id),
        "username": user.username,
        "nickname": user.nickname or user.username,
        "email": user.email or "",
        "avatar": getattr(user, "avatar", ""),
        "roles": get_user_roles(user.id),
        "perms": get_user_permissions(user.id),
    }


def _ensure_admin():
    """确保管理员账号存在（启动时调用）"""
    exists = SysUser.query.filter_by(username="mubai").first()
    if not exists:
        admin = SysUser(
            username="mubai",
            password_hash=generate_password_hash("huanxin0321"),
            email="",
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if SysUser.query.filter_by(username=data["username"]).first():
        return error(msg="用户名已存在", code="400")

    user = SysUser(
        username=data["username"],
        password_hash=generate_password_hash(data["password"]),
        email=data.get("email", ""),
        nickname=data.get("nickname", data["username"]),
    )
    db.session.add(user)
    db.session.commit()
    return success(msg="注册成功")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    # 优先从 SysUser 查询，回退到旧 User 表
    user = SysUser.query.filter_by(username=data["username"]).first()
    if not user:
        try:
            from app.models.user import User
            old_user = User.query.filter_by(username=data["username"]).first()
            if old_user:
                user = SysUser(
                    username=old_user.username,
                    password_hash=old_user.password_hash,
                    email=old_user.email,
                    identity="admin" if old_user.role == "admin" else "member",
                    is_admin=1 if old_user.role == "admin" else 0,
                )
                db.session.add(user)
                db.session.flush()
        except (ImportError, ModuleNotFoundError):
            pass

    if not user or not check_password_hash(user.password_hash, data["password"]):
        return error(msg="用户名或密码错误", code="A0300")

    if getattr(user, "status", 1) == 0:
        return error(msg="账号已被禁用", code="A0301")

    # 更新登录信息
    user.login_ip = request.remote_addr
    from datetime import datetime
    user.login_date = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=str(user.id), additional_claims={"role": user.identity or "member"})
    refresh_token = create_refresh_token(identity=str(user.id))

    return success(data={
        "accessToken": access_token,
        "refreshToken": refresh_token,
    }, msg="登录成功")


@auth_bp.route("/refresh-token", methods=["POST"])
def refresh_token_endpoint():
    refresh_token = request.args.get("refresh_token")
    if not refresh_token:
        return error(msg="缺少 refresh token", code="A0231")

    try:
        from flask_jwt_extended import decode_token
        decoded = decode_token(refresh_token)
        user_id = decoded.get("sub")
        if not user_id:
            return error(msg="Refresh token 无效", code="A0231")
    except Exception:
        return error(msg="Refresh token 无效", code="A0231")

    new_access_token = create_access_token(identity=user_id)
    return success(data={"accessToken": new_access_token})


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    return success(msg="退出成功")


@auth_bp.route("/info", methods=["GET"])
@jwt_required()
def get_user_info():
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    user = SysUser.query.get(user_id)
    if not user:
        return error(msg="用户不存在", code="A0400")
    return success(data=_build_user_info(user))
