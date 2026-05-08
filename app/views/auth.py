from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"message": "用户名已存在"}), 400

    user = User(
        username=data["username"],
        password_hash=generate_password_hash(data["password"]),
        email=data.get("email", ""),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "注册成功"}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data["username"]).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"message": "用户名或密码错误"}), 401

    token = create_access_token(identity=user.id)
    return jsonify({"access_token": token, "user_id": user.id})
