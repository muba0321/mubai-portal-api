from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.utils.response import success, error
from datetime import datetime

ansible_bp = Blueprint("ansible", __name__)

@ansible_bp.route("/ping", methods=["GET"])
@jwt_required()
def ping_all():
    return success(data={
        "total": 5,
        "reachable": 5,
        "unreachable": 0,
        "results": [
            {"host": "web-server-01", "status": "reachable", "ping_ms": 2},
            {"host": "db-server-01", "status": "reachable", "ping_ms": 1},
            {"host": "cache-server-01", "status": "reachable", "ping_ms": 1},
            {"host": "monitor-server-01", "status": "reachable", "ping_ms": 3},
            {"host": "jenkins-server-01", "status": "reachable", "ping_ms": 5},
        ]
    })

@ansible_bp.route("/inventory", methods=["GET"])
@jwt_required()
def get_inventory():
    groups = request.args.get("group", "")
    groups_param = request.args.get("groups", "")
    return success(data={
        "groups": {
            "webservers": {
                "hosts": ["web-server-01", "web-server-02"],
                "vars": {"http_port": 80, "ansible_user": "root"}
            },
            "dbservers": {
                "hosts": ["db-server-01"],
                "vars": {"db_port": 3306, "ansible_user": "root"}
            },
            "cacheservers": {
                "hosts": ["cache-server-01"],
                "vars": {"cache_port": 6379, "ansible_user": "root"}
            },
            "monitorservers": {
                "hosts": ["monitor-server-01"],
                "vars": {"ansible_user": "root"}
            },
            "jenkinsservers": {
                "hosts": ["jenkins-server-01"],
                "vars": {"ansible_user": "root"}
            },
            "all": {
                "hosts": ["web-server-01", "web-server-02", "db-server-01", "cache-server-01", "monitor-server-01", "jenkins-server-01"],
                "vars": {"ansible_user": "root"}
            }
        },
        "hosts": {
            "web-server-01": {"ansible_host": "192.168.1.101", "os": "Ubuntu 22.04", "cpu": 4, "memory": "8GB"},
            "web-server-02": {"ansible_host": "192.168.1.102", "os": "Ubuntu 22.04", "cpu": 4, "memory": "8GB"},
            "db-server-01": {"ansible_host": "192.168.1.201", "os": "CentOS 8", "cpu": 8, "memory": "32GB"},
            "cache-server-01": {"ansible_host": "192.168.1.301", "os": "Ubuntu 22.04", "cpu": 2, "memory": "4GB"},
            "monitor-server-01": {"ansible_host": "192.168.1.401", "os": "Ubuntu 22.04", "cpu": 4, "memory": "16GB"},
            "jenkins-server-01": {"ansible_host": "192.168.1.501", "os": "CentOS 8", "cpu": 4, "memory": "8GB"},
        }
    })

@ansible_bp.route("/jobs", methods=["GET"])
@jwt_required()
def list_jobs():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    jobs = [
        {"id": 1, "name": "部署应用到 web-server-01", "status": "success", "host": "web-server-01", "playbook": "deploy-app.yml", "started_at": "2026-06-11 14:30:00", "duration": "45s"},
        {"id": 2, "name": "重启 Nginx 服务", "status": "success", "host": "web-server-01", "playbook": "restart-nginx.yml", "started_at": "2026-06-11 10:15:00", "duration": "12s"},
        {"id": 3, "name": "MySQL 备份", "status": "success", "host": "db-server-01", "playbook": "mysql-backup.yml", "started_at": "2026-06-11 03:00:00", "duration": "180s"},
        {"id": 4, "name": "更新系统补丁", "status": "running", "host": "all", "playbook": "system-update.yml", "started_at": "2026-06-11 20:00:00", "duration": "-"},
        {"id": 5, "name": "清理日志文件", "status": "failed", "host": "web-server-02", "playbook": "cleanup-logs.yml", "started_at": "2026-06-10 22:00:00", "duration": "5s"},
    ]
    start = (page - 1) * per_page
    end = start + per_page
    return success(data={
        "total": len(jobs),
        "page": page,
        "per_page": per_page,
        "items": jobs[start:end]
    })

@ansible_bp.route("/jobs", methods=["POST"])
@jwt_required()
def create_job():
    data = request.get_json() or {}
    return success(data={"job_id": 6, "status": "queued"})

@ansible_bp.route("/jobs/<int:job_id>", methods=["GET"])
@jwt_required()
def get_job(job_id):
    return success(data={
        "id": job_id,
        "name": "作业详情",
        "status": "success",
        "host": "web-server-01",
        "playbook": "deploy-app.yml",
        "started_at": "2026-06-11 14:30:00",
        "duration": "45s",
        "output": "PLAY [Deploy Application]... ok=5 changed=2 unreachable=0 failed=0"
    })

@ansible_bp.route("/schedules", methods=["GET"])
@jwt_required()
def list_schedules():
    schedules = [
        {"id": 1, "name": "MySQL 每日备份", "playbook": "mysql-backup.yml", "cron": "0 3 * * *", "enabled": True, "hosts": "dbservers", "last_run": "2026-06-11 03:00:00", "next_run": "2026-06-12 03:00:00"},
        {"id": 2, "name": "系统每日更新", "playbook": "system-update.yml", "cron": "0 2 * * 0", "enabled": True, "hosts": "all", "last_run": "2026-06-08 02:00:00", "next_run": "2026-06-15 02:00:00"},
        {"id": 3, "name": "日志清理", "playbook": "cleanup-logs.yml", "cron": "0 4 * * *", "enabled": False, "hosts": "webservers", "last_run": "2026-06-09 04:00:00", "next_run": "-"},
    ]
    return success(data=schedules)

@ansible_bp.route("/schedules", methods=["POST"])
@jwt_required()
def create_schedule():
    data = request.get_json() or {}
    return success(data={"schedule_id": 4, "status": "created"})

@ansible_bp.route("/schedules/<int:schedule_id>/toggle", methods=["PUT"])
@jwt_required()
def toggle_schedule(schedule_id):
    return success(data={"schedule_id": schedule_id, "enabled": True})
