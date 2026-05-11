from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.sys import SysMonitor, SysCommonLink, SysRecentVisit
from app.utils.response import success

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/system-status", methods=["GET"])
@jwt_required()
def system_status():
    record = SysMonitor.query.order_by(SysMonitor.created_at.desc()).first()
    if not record:
        return success(data={
            "server_online": 0, "service_running": 0,
            "network_status": "normal", "storage_usage": "0%",
            "alert_pending": 0, "cpu_load": "0%",
            "last_updated": None,
        })

    return success(data={
        "server_online": record.server_online,
        "service_running": record.service_running,
        "network_status": record.network_status,
        "storage_usage": record.storage_usage,
        "alert_pending": record.alert_pending,
        "cpu_load": record.cpu_load,
        "last_updated": record.snapshot_time,
    })


@dashboard_bp.route("/common-links", methods=["GET"])
@jwt_required()
def common_links():
    links = SysCommonLink.query.filter_by(enabled=1).order_by(SysCommonLink.sort).all()
    data = [
        {
            "id": link.id,
            "title": link.title,
            "description": link.description,
            "url": link.url,
            "icon": link.icon,
            "sort": link.sort,
        }
        for link in links
    ]
    return success(data=data)


@dashboard_bp.route("/recent-visits", methods=["GET"])
@jwt_required()
def get_recent_visits():
    user_id = int(get_jwt_identity())
    visits = (
        SysRecentVisit.query.filter_by(user_id=user_id)
        .order_by(SysRecentVisit.visited_at.desc())
        .limit(4)
        .all()
    )
    data = [
        {
            "page_path": v.page_path,
            "page_title": v.page_title,
            "visited_at": v.visited_at,
        }
        for v in visits
    ]
    return success(data=data)


@dashboard_bp.route("/recent-visits", methods=["POST"])
@jwt_required()
def create_recent_visit():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    page_path = data.get("pagePath", "")
    page_title = data.get("pageTitle", "")

    existing = SysRecentVisit.query.filter_by(
        user_id=user_id, page_path=page_path
    ).first()
    if existing:
        from datetime import datetime
        existing.visited_at = datetime.now()
        existing.page_title = page_title
    else:
        visit = SysRecentVisit(
            user_id=user_id, page_path=page_path, page_title=page_title,
        )
        db.session.add(visit)
    db.session.commit()
    return success()
