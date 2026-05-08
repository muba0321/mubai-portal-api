from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.service import Service
from marshmallow import Schema, fields

service_bp = Blueprint("service", __name__)


class ServiceSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String()
    description = fields.String()
    owner = fields.String()
    url = fields.String()
    status = fields.String()
    created_at = fields.DateTime(dump_only=True)


@service_bp.route("", methods=["GET"])
@jwt_required()
def list_services():
    services = Service.query.all()
    return jsonify(ServiceSchema(many=True).dump(services))


@service_bp.route("", methods=["POST"])
@jwt_required()
def create_service():
    data = request.get_json()
    service = Service(**data)
    db.session.add(service)
    db.session.commit()
    return jsonify(ServiceSchema().dump(service)), 201


@service_bp.route("/<int:service_id>", methods=["GET"])
@jwt_required()
def get_service(service_id):
    service = Service.query.get_or_404(service_id)
    return jsonify(ServiceSchema().dump(service))


@service_bp.route("/<int:service_id>", methods=["PUT"])
@jwt_required()
def update_service(service_id):
    service = Service.query.get_or_404(service_id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(service, key):
            setattr(service, key, value)
    db.session.commit()
    return jsonify(ServiceSchema().dump(service))


@service_bp.route("/<int:service_id>", methods=["DELETE"])
@jwt_required()
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    return jsonify({"message": "删除成功"})
