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
            "category": link.category,
            "sort": link.sort,
        }
        for link in links
    ]
    return success(data=data)


@dashboard_bp.route("/common-links", methods=["POST"])
@jwt_required()
def create_common_link():
    data = request.get_json()
    link = SysCommonLink(
        title=data.get("title", ""),
        description=data.get("description", ""),
        url=data.get("url", ""),
        icon=data.get("icon", "Link"),
        category=data.get("category"),
        sort=int(data.get("sort", 0)),
        enabled=1,
    )
    db.session.add(link)
    db.session.commit()
    return success(data={"id": link.id}, msg="添加成功")


@dashboard_bp.route("/common-links/<int:link_id>", methods=["PUT"])
@jwt_required()
def update_common_link(link_id):
    link = SysCommonLink.query.get(link_id)
    if not link:
        from app.utils.response import error
        return error(msg="链接不存在", code="40400")
    data = request.get_json()
    link.title = data.get("title", link.title)
    link.description = data.get("description", link.description)
    link.url = data.get("url", link.url)
    link.icon = data.get("icon", link.icon)
    link.category = data.get("category", link.category)
    link.sort = int(data.get("sort", link.sort))
    link.enabled = int(data.get("enabled", link.enabled))
    db.session.commit()
    return success(msg="修改成功")


@dashboard_bp.route("/common-links/<int:link_id>", methods=["DELETE"])
@jwt_required()
def delete_common_link(link_id):
    link = SysCommonLink.query.get(link_id)
    if not link:
        from app.utils.response import error
        return error(msg="链接不存在", code="40400")
    db.session.delete(link)
    db.session.commit()
    return success(msg="删除成功")


def _auto_categorize(title, url):
    t = (title or "").lower()
    u = (url or "").lower()
    if any(k in t for k in ["监控", "grafana", "prometheus", "大盘", "告警"]):
        return "监控工具"
    if any(k in t for k in ["cmdb", "dns", "系统配置", "系统设置", "设置", "配置", "极客", "管理"]):
        return "运维管理"
    if any(k in t for k in ["coding", "开发", "openclaw", "ci", "jenkins", "git"]):
        return "开发工具"
    if any(k in t for k in ["文档", "资料", "飞书", "帮助", "help", "doc"]):
        return "文档资料"
    return "其他"


@dashboard_bp.route("/common-links/auto-categorize", methods=["POST"])
@jwt_required()
def auto_categorize_links():
    links = SysCommonLink.query.filter(SysCommonLink.category == None).all()
    updated = 0
    for link in links:
        cat = _auto_categorize(link.title, link.url)
        if cat != "其他":
            link.category = cat
            updated += 1
    db.session.commit()
    return success(data={"updated": updated})


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
