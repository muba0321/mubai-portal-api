from flask import Blueprint, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required
from werkzeug.security import check_password_hash
from app.extensions import db
from app.models.sys import SysUser
from app.utils.response import success, error

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")

    user = SysUser.query.filter_by(username=username, deleted=0).first()
    if not user or not check_password_hash(user.password_hash, password):
        return error(msg="用户名或密码错误", code="A0300")

    access_token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    refresh_token = create_refresh_token(identity=str(user.id))

    return success(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
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
    return success(data={"access_token": new_access_token})


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    return success(msg="退出成功")
