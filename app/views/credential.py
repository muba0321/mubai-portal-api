"""
密码管理 API
"""
import base64
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.credential import Credential
from app.utils.response import success, error

credential_bp = Blueprint("credential", __name__)

# 简单的加密/解密（实际生产应使用更强的加密）
SECRET_KEY = "sre-portal-credential-key-2026"


def encrypt_password(password: str) -> str:
    """简单加密密码"""
    if not password:
        return ""
    encoded = password.encode("utf-8")
    # 异或加密 + base64
    key = SECRET_KEY.encode("utf-8")
    encrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(encoded)])
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_password(encrypted: str) -> str:
    """解密密码"""
    if not encrypted:
        return ""
    try:
        decoded = base64.b64decode(encrypted)
        key = SECRET_KEY.encode("utf-8")
        decrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(decoded)])
        return decrypted.decode("utf-8")
    except Exception:
        return ""


def get_current_user():
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    from app.models.sys_user import SysUser
    user = SysUser.query.get(user_id)
    return user.username if user else "admin"


@credential_bp.route("/credentials", methods=["GET"])
@jwt_required()
def list_credentials():
    """获取密码列表（密码字段返回星号）"""
    category = request.args.get("category")
    keyword = request.args.get("keyword")

    q = Credential.query

    if category:
        q = q.filter_by(category=category)
    if keyword:
        q = q.filter(Credential.name.like(f"%{keyword}%"))

    items = q.order_by(Credential.updated_at.desc()).all()

    return success(data=[{
        "id": c.id,
        "name": c.name,
        "category": c.category,
        "url": c.url,
        "username": c.username,
        "password": "********",  # 不返回真实密码
        "remark": c.remark,
        "createdBy": c.created_by,
        "createdAt": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else None,
    } for c in items])


@credential_bp.route("/credentials", methods=["POST"])
@jwt_required()
def create_credential():
    """新增密码记录"""
    data = request.get_json()
    if not data.get("name"):
        return error(msg="服务名称不能为空")

    credential = Credential(
        name=data["name"],
        category=data.get("category", "other"),
        url=data.get("url", ""),
        username=data.get("username", ""),
        password=encrypt_password(data.get("password", "")),
        remark=data.get("remark", ""),
        created_by=get_current_user(),
    )
    db.session.add(credential)
    db.session.commit()

    return success(data={"id": credential.id}, msg="创建成功")


@credential_bp.route("/credentials/<int:cred_id>", methods=["GET"])
@jwt_required()
def get_credential(cred_id):
    """获取密码详情（返回解密后的密码）"""
    credential = Credential.query.get(cred_id)
    if not credential:
        return error(msg="记录不存在")

    return success(data={
        "id": credential.id,
        "name": credential.name,
        "category": credential.category,
        "url": credential.url,
        "username": credential.username,
        "password": decrypt_password(credential.password),  # 返回真实密码
        "remark": credential.remark,
        "createdBy": credential.created_by,
        "createdAt": credential.created_at.strftime("%Y-%m-%d %H:%M:%S") if credential.created_at else None,
    })


@credential_bp.route("/credentials/<int:cred_id>", methods=["PUT"])
@jwt_required()
def update_credential(cred_id):
    """更新密码记录"""
    credential = Credential.query.get(cred_id)
    if not credential:
        return error(msg="记录不存在")

    data = request.get_json()
    if "name" in data:
        credential.name = data["name"]
    if "category" in data:
        credential.category = data["category"]
    if "url" in data:
        credential.url = data["url"]
    if "username" in data:
        credential.username = data["username"]
    if "password" in data:
        credential.password = encrypt_password(data["password"])
    if "remark" in data:
        credential.remark = data["remark"]

    db.session.commit()
    return success(msg="更新成功")


@credential_bp.route("/credentials/<int:cred_id>", methods=["DELETE"])
@jwt_required()
def delete_credential(cred_id):
    """删除密码记录"""
    credential = Credential.query.get(cred_id)
    if not credential:
        return error(msg="记录不存在")

    db.session.delete(credential)
    db.session.commit()
    return success(msg="删除成功")


@credential_bp.route("/credentials/categories", methods=["GET"])
@jwt_required()
def list_categories():
    """获取分类列表"""
    categories = [
        {"value": "server", "label": "服务器", "icon": "Monitor"},
        {"value": "database", "label": "数据库", "icon": "DataBoard"},
        {"value": "website", "label": "网站", "icon": "Link"},
        {"value": "api", "label": "API", "icon": "Connection"},
        {"value": "other", "label": "其他", "icon": "Files"},
    ]
    return success(data=categories)
