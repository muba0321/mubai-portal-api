"""
Jenkins 管理 API
提供流水线管理、节点管理、队列管理等功能
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.utils.response import success, error
from app.utils.jenkins_client import jenkins_client

jenkins_bp = Blueprint("jenkins", __name__)


# ==================== 流水线管理 ====================

@jenkins_bp.route("/pipelines", methods=["GET"])
@jwt_required()
def get_pipelines():
    """获取所有流水线列表"""
    data = jenkins_client.get_jobs()
    if "error" in data:
        return error(msg=data["error"])

    jobs = data.get("jobs", [])
    result = []
    for job in jobs:
        last_build = job.get("lastBuild")
        result.append({
            "name": job.get("name"),
            "displayName": job.get("displayName"),
            "color": job.get("color"),
            "healthScore": job.get("healthScore", [{}])[0].get("score", 0) if job.get("healthScore") else 0,
            "lastBuild": {
                "number": last_build.get("number") if last_build else None,
                "status": last_build.get("status") if last_build else None,
                "timestamp": last_build.get("timestamp") if last_build else None
            } if last_build else None
        })

    return success(data=result)


@jenkins_bp.route("/pipelines/<job_name>/build", methods=["POST"])
@jwt_required()
def trigger_pipeline_build(job_name):
    """触发流水线构建"""
    data = request.get_json() or {}
    parameters = data.get("parameters")

    result = jenkins_client.trigger_build(job_name, parameters)
    if "error" in result:
        return error(msg=result["error"])

    return success(data={"message": "构建已触发", "queueId": result.get("id")})


@jenkins_bp.route("/pipelines/<job_name>/builds", methods=["GET"])
@jwt_required()
def get_pipeline_builds(job_name):
    """获取流水线构建历史"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)

    data = jenkins_client.get_builds(job_name, limit=page_size * page)
    if "error" in data:
        return error(msg=data["error"])

    builds = data.get("builds", [])
    # 分页处理
    start = (page - 1) * page_size
    end = start + page_size
    paginated_builds = builds[start:end]

    result = []
    for build in paginated_builds:
        result.append({
            "number": build.get("number"),
            "status": build.get("status"),
            "duration": build.get("duration"),
            "timestamp": build.get("timestamp"),
            "url": build.get("url")
        })

    return success(data={
        "list": result,
        "total": len(builds),
        "page": page,
        "pageSize": page_size
    })


@jenkins_bp.route("/pipelines/<job_name>/builds/<int:build_number>", methods=["GET"])
@jwt_required()
def get_build_detail(job_name, build_number):
    """获取构建详情"""
    data = jenkins_client.get_build_detail(job_name, build_number)
    if "error" in data:
        return error(msg=data["error"])

    return success(data=data)


@jenkins_bp.route("/pipelines/<job_name>/builds/<int:build_number>/log", methods=["GET"])
@jwt_required()
def get_build_log(job_name, build_number):
    """获取构建日志"""
    data = jenkins_client.get_build_log(job_name, build_number)
    if "error" in data:
        return error(msg=data["error"])

    return success(data=data)


# ==================== 节点管理 ====================

@jenkins_bp.route("/nodes", methods=["GET"])
@jwt_required()
def get_nodes():
    """获取所有节点列表"""
    data = jenkins_client.get_nodes()
    if "error" in data:
        return error(msg=data["error"])

    computers = data.get("computer", [])
    result = []
    for computer in computers:
        result.append({
            "name": computer.get("displayName"),
            "displayName": computer.get("displayName"),
            "offline": computer.get("offline"),
            "numExecutors": computer.get("numExecutors"),
            "numExecutorsBusy": computer.get("numExecutorsBusy")
        })

    return success(data=result)


@jenkins_bp.route("/nodes/<node_name>", methods=["GET"])
@jwt_required()
def get_node_detail(node_name):
    """获取节点详情"""
    data = jenkins_client.get_node_info(node_name)
    if "error" in data:
        return error(msg=data["error"])

    return success(data=data)


# ==================== 队列管理 ====================

@jenkins_bp.route("/queue", methods=["GET"])
@jwt_required()
def get_queue():
    """获取当前构建队列"""
    data = jenkins_client.get_queue()
    if "error" in data:
        return error(msg=data["error"])

    items = data.get("items", [])
    result = []
    for item in items:
        task = item.get("task", {})
        result.append({
            "id": item.get("id"),
            "task": {
                "name": task.get("name"),
                "url": task.get("url")
            },
            "stuck": item.get("stuck"),
            "why": item.get("why"),
            "timestamp": item.get("timestamp")
        })

    return success(data=result)
