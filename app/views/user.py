from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.user import User
from marshmallow import Schema, fields

user_bp = Blueprint("user", __name__)


class UserSchema(Schema):
    id = fields.Integer(dump_only=True)
    username = fields.String()
    email = fields.String()
    role = fields.String()


@user_bp.route("", methods=["GET"])
@jwt_required()
def list_users():
    users = User.query.all()
    return jsonify(UserSchema(many=True).dump(users))


@user_bp.route("/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(UserSchema().dump(user))


@user_bp.route("/<int:user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    if "email" in data:
        user.email = data["email"]
    if "role" in data:
        user.role = data["role"]
    db.session.commit()
    return jsonify(UserSchema().dump(user))


@user_bp.route("/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "删除成功"})
