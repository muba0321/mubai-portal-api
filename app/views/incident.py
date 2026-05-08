from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.incident import Incident
from marshmallow import Schema, fields

incident_bp = Blueprint("incident", __name__)


class IncidentSchema(Schema):
    id = fields.Integer(dump_only=True)
    title = fields.String()
    description = fields.String()
    severity = fields.String()
    status = fields.String()
    reporter = fields.String()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


@incident_bp.route("", methods=["GET"])
@jwt_required()
def list_incidents():
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return jsonify(IncidentSchema(many=True).dump(incidents))


@incident_bp.route("", methods=["POST"])
@jwt_required()
def create_incident():
    data = request.get_json()
    incident = Incident(**data)
    db.session.add(incident)
    db.session.commit()
    return jsonify(IncidentSchema().dump(incident)), 201


@incident_bp.route("/<int:incident_id>", methods=["GET"])
@jwt_required()
def get_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    return jsonify(IncidentSchema().dump(incident))


@incident_bp.route("/<int:incident_id>", methods=["PUT"])
@jwt_required()
def update_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(incident, key):
            setattr(incident, key, value)
    db.session.commit()
    return jsonify(IncidentSchema().dump(incident))
