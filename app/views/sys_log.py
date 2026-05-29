from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.models.sys_oper_log import OperLog
from app.utils.permission import require_permission, success_response

sys_log_bp = Blueprint("sys_log", __name__)


def log_to_dict(l):
    return {
        "id": str(l.id),
        "title": l.module or "",
        "ip": l.ip or "",
        "requestUri": l.method or "",
        "requestMethod": l.request_method or "",
        "executionTime": 0,
        "operatorName": l.username or "",
        "createTime": l.created_at.isoformat() if l.created_at else None,
        "status": l.status,
        "errorMsg": l.error_msg or "",
    }


@sys_log_bp.route("", methods=["GET"])
@jwt_required()
@require_permission("sys:log:list")
def list_logs():
    keywords = request.args.get("keywords", "")
    page_num = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 10, type=int)

    query = OperLog.query
    if keywords:
        query = query.filter(
            OperLog.ip.contains(keywords) |
            OperLog.username.contains(keywords)
        )

    total = query.count()
    logs = query.order_by(OperLog.created_at.desc()).offset((page_num - 1) * page_size).limit(page_size).all()
    return success_response({"list": [log_to_dict(l) for l in logs], "total": total})
