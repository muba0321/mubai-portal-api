"""
运维中心 API
真实 SSH 执行 + CMDB 主机清单 + 作业历史 + 定时任务 + 快捷命令
"""
import json
import time
from datetime import datetime
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.utils.response import success, error
from app.utils.ssh_runner import SSHRunner
from app.config import Config

ansible_bp = Blueprint("ansible", __name__)

# SSH 密钥路径（从配置读取）
SSH_KEY = Config.__dict__.get("SSH_KEY_PATH", "/root/.ssh/sre_portal_key")


def _get_runner():
    """获取 SSH 执行器"""
    return SSHRunner(key_file=SSH_KEY)


def _get_current_user():
    """获取当前用户名"""
    try:
        user_id = get_jwt_identity()
        if isinstance(user_id, str):
            user_id = int(user_id)
        from app.models.sys_user import SysUser
        user = SysUser.query.get(user_id)
        return user.username if user else "admin"
    except:
        return "admin"


def _get_targets_from_request(data):
    """从请求中解析目标主机列表"""
    hosts = data.get("hosts", [])
    if not hosts:
        # 如果没指定，默认全部 CMDB 在线主机
        from app.models.cmdb_vm import CmdbVM
        vms = CmdbVM.query.filter_by(deleted=0, status=1).all()
        hosts = [vm.external_ip for vm in vms]
    return hosts


# ==================== 主机清单 ====================

@ansible_bp.route("/ping", methods=["GET"])
@jwt_required()
def ping_all():
    """批量 Ping 检测主机连通性"""
    from app.models.cmdb_vm import CmdbVM
    vms = CmdbVM.query.filter_by(deleted=0).all()

    runner = _get_runner()
    results = []
    reachable = 0
    unreachable = 0

    for vm in vms:
        is_reachable = runner.ping_host(vm.external_ip)
        status = "reachable" if is_reachable else "unreachable"
        if is_reachable:
            reachable += 1
        else:
            unreachable += 1
        results.append({
            "host": vm.name,
            "ip": vm.external_ip,
            "status": status,
            "cluster": vm.cluster,
        })

    return success(data={
        "total": len(vms),
        "reachable": reachable,
        "unreachable": unreachable,
        "results": results,
    })


@ansible_bp.route("/inventory", methods=["GET"])
@jwt_required()
def get_inventory():
    """获取主机清单（从 CMDB 读取，按集群分组）"""
    from app.models.cmdb_vm import CmdbVM

    group_filter = request.args.get("group", "")
    vms = CmdbVM.query.filter_by(deleted=0)
    if group_filter:
        vms = vms.filter_by(cluster=group_filter)
    vms = vms.all()

    # 按集群分组
    groups = {}
    hosts_detail = {}

    for vm in vms:
        cluster = vm.cluster or "default"
        if cluster not in groups:
            groups[cluster] = {"hosts": [], "vars": {}}
        groups[cluster]["hosts"].append(vm.name)

        hosts_detail[vm.name] = {
            "ansible_host": vm.external_ip,
            "internal_ip": vm.internal_ip,
            "os": "Linux",
            "cpu": vm.vcpus,
            "memory": f"{vm.memory // 1024}GB",
            "status": "online" if vm.status == 1 else "offline",
            "cluster": cluster,
            "access_url": vm.access_url or "",
        }

    # 添加 all 组
    all_hosts = [vm.name for vm in vms]
    groups["all"] = {"hosts": all_hosts, "vars": {}}

    return success(data={
        "groups": groups,
        "hosts": hosts_detail,
        "clusters": list(set(vm.cluster for vm in vms if vm.cluster)),
    })


# ==================== 快捷命令模板 ====================

@ansible_bp.route("/commands", methods=["GET"])
@jwt_required()
def list_commands():
    """获取快捷命令模板列表"""
    from app.models.ansible_job import AnsibleCommand

    category = request.args.get("category", "")
    q = AnsibleCommand.query.filter_by(enabled=True)
    if category:
        q = q.filter_by(category=category)
    commands = q.order_by(AnsibleCommand.sort).all()

    result = []
    for c in commands:
        result.append({
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "command": c.command,
            "description": c.description,
            "module": c.module,
        })

    return success(data=result)


@ansible_bp.route("/commands", methods=["POST"])
@jwt_required()
def create_command():
    """创建快捷命令模板"""
    from app.models.ansible_job import AnsibleCommand

    data = request.get_json()
    if not data or not data.get("name") or not data.get("command"):
        return error(msg="name 和 command 不能为空")

    cmd = AnsibleCommand(
        name=data["name"],
        category=data.get("category", "custom"),
        command=data["command"],
        description=data.get("description", ""),
        module=data.get("module", "shell"),
        sort=data.get("sort", 0),
    )
    db.session.add(cmd)
    db.session.commit()

    return success(data={"id": cmd.id}, msg="创建成功")


@ansible_bp.route("/commands/<int:cmd_id>", methods=["DELETE"])
@jwt_required()
def delete_command(cmd_id):
    """删除快捷命令模板"""
    from app.models.ansible_job import AnsibleCommand

    cmd = AnsibleCommand.query.get(cmd_id)
    if not cmd:
        return error(msg="命令不存在")

    db.session.delete(cmd)
    db.session.commit()
    return success(msg="删除成功")


# ==================== 作业执行 ====================

@ansible_bp.route("/jobs", methods=["POST"])
@jwt_required()
def create_job():
    """创建并执行作业"""
    from app.models.ansible_job import AnsibleJob

    data = request.get_json()
    if not data:
        return error(msg="请求体不能为空")

    command = data.get("command", "").strip()
    if not command:
        return error(msg="命令不能为空")

    # 安全检查
    is_safe, msg = SSHRunner.validate_command(command)
    if not is_safe:
        return error(msg=f"命令安全检查未通过: {msg}")

    # 变量替换
    extra_vars = data.get("extra_vars", {})
    command = SSHRunner.replace_variables(command, extra_vars)

    # 获取目标主机
    hosts = _get_targets_from_request(data)
    if not hosts:
        return error(msg="未找到可用的目标主机")

    username = _get_current_user()

    # 创建作业记录
    job = AnsibleJob(
        job_name=data.get("name", command[:50]),
        job_type=data.get("job_type", "ad_hoc"),
        module=data.get("module", "shell"),
        module_args=command,
        targets=json.dumps(hosts, ensure_ascii=False),
        extra_vars=json.dumps(extra_vars, ensure_ascii=False) if extra_vars else None,
        status="running",
        created_by=username,
        started_at=datetime.now(),
    )
    db.session.add(job)
    db.session.commit()

    # 执行命令
    runner = _get_runner()
    start_time = time.time()

    if len(hosts) == 1:
        # 单机执行
        result = runner.exec_on_host(hosts[0], command)
        results = {hosts[0]: result}
    else:
        # 批量执行
        results = runner.exec_batch(hosts, command)

    duration = int(time.time() - start_time)

    # 统计结果
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    fail_count = sum(1 for r in results.values() if r["status"] != "success")

    # 更新作业记录
    job.status = "success" if fail_count == 0 else "partial" if success_count > 0 else "failed"
    job.finished_at = datetime.now()
    job.duration = duration
    job.result = json.dumps(results, ensure_ascii=False)

    db.session.commit()

    return success(data={
        "job_id": job.id,
        "status": job.status,
        "duration": duration,
        "total_hosts": len(hosts),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
    })


@ansible_bp.route("/jobs", methods=["GET"])
@jwt_required()
def list_jobs():
    """获取作业历史列表"""
    from app.models.ansible_job import AnsibleJob

    page = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)
    status_filter = request.args.get("status", "")

    q = AnsibleJob.query
    if status_filter:
        q = q.filter_by(status=status_filter)

    total = q.count()
    jobs = q.order_by(AnsibleJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for job in jobs:
        targets = json.loads(job.targets) if job.targets else []
        result.append({
            "id": job.id,
            "jobName": job.job_name,
            "jobType": job.job_type,
            "module": job.module,
            "targets": targets,
            "status": job.status,
            "createdBy": job.created_by,
            "startedAt": job.started_at.strftime("%Y-%m-%d %H:%M:%S") if job.started_at else None,
            "duration": job.duration,
            "createdAt": job.created_at.strftime("%Y-%m-%d %H:%M:%S") if job.created_at else None,
        })

    return success(data={"total": total, "list": result})


@ansible_bp.route("/jobs/<int:job_id>", methods=["GET"])
@jwt_required()
def get_job(job_id):
    """获取作业详情"""
    from app.models.ansible_job import AnsibleJob

    job = AnsibleJob.query.get(job_id)
    if not job:
        return error(msg="作业不存在")

    targets = json.loads(job.targets) if job.targets else []
    results = json.loads(job.result) if job.result else {}
    extra_vars = json.loads(job.extra_vars) if job.extra_vars else {}

    return success(data={
        "id": job.id,
        "jobName": job.job_name,
        "jobType": job.job_type,
        "module": job.module,
        "moduleArgs": job.module_args,
        "targets": targets,
        "extraVars": extra_vars,
        "status": job.status,
        "createdBy": job.created_by,
        "startedAt": job.started_at.strftime("%Y-%m-%d %H:%M:%S") if job.started_at else None,
        "finishedAt": job.finished_at.strftime("%Y-%m-%d %H:%M:%S") if job.finished_at else None,
        "duration": job.duration,
        "results": results,
        "errorMsg": job.error_msg,
        "createdAt": job.created_at.strftime("%Y-%m-%d %H:%M:%S") if job.created_at else None,
    })


# ==================== 定时任务 ====================

@ansible_bp.route("/schedules", methods=["GET"])
@jwt_required()
def list_schedules():
    """获取定时任务列表"""
    from app.models.ansible_job import AnsibleSchedule

    schedules = AnsibleSchedule.query.order_by(AnsibleSchedule.created_at.desc()).all()
    result = []
    for s in schedules:
        result.append({
            "id": s.id,
            "name": s.name,
            "taskType": s.task_type or "command",
            "command": s.command,
            "jobId": s.job_id,
            "cronExpression": s.cron_expression,
            "enabled": s.enabled,
            "lastRun": s.last_run.strftime("%Y-%m-%d %H:%M:%S") if s.last_run else None,
            "lastStatus": s.last_status,
            "createdBy": s.created_by,
            "createdAt": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else None,
        })

    return success(data=result)


@ansible_bp.route("/schedules", methods=["POST"])
@jwt_required()
def create_schedule():
    """创建定时任务"""
    from app.models.ansible_job import AnsibleSchedule

    data = request.get_json()
    if not data or not data.get("name") or not data.get("cronExpression"):
        return error(msg="name 和 cronExpression 不能为空")

    schedule = AnsibleSchedule(
        name=data["name"],
        task_type=data.get("taskType", "command"),
        command=data.get("command"),
        job_id=data.get("jobId"),
        cron_expression=data["cronExpression"],
        enabled=data.get("enabled", True),
        created_by=_get_current_user(),
    )
    db.session.add(schedule)
    db.session.commit()

    return success(data={"id": schedule.id}, msg="创建成功")


@ansible_bp.route("/schedules/<int:schedule_id>", methods=["PUT"])
@jwt_required()
def update_schedule(schedule_id):
    """更新定时任务"""
    from app.models.ansible_job import AnsibleSchedule

    schedule = AnsibleSchedule.query.get(schedule_id)
    if not schedule:
        return error(msg="定时任务不存在")

    data = request.get_json()
    if "enabled" in data:
        schedule.enabled = data["enabled"]
    if "cronExpression" in data:
        schedule.cron_expression = data["cronExpression"]
    if "name" in data:
        schedule.name = data["name"]
    if "taskType" in data:
        schedule.task_type = data["taskType"]
    if "command" in data:
        schedule.command = data["command"]

    db.session.commit()
    return success(msg="更新成功")


@ansible_bp.route("/schedules/<int:schedule_id>", methods=["DELETE"])
@jwt_required()
def delete_schedule(schedule_id):
    """删除定时任务"""
    from app.models.ansible_job import AnsibleSchedule

    schedule = AnsibleSchedule.query.get(schedule_id)
    if not schedule:
        return error(msg="定时任务不存在")

    db.session.delete(schedule)
    db.session.commit()
    return success(msg="删除成功")


@ansible_bp.route("/schedules/<int:schedule_id>/toggle", methods=["PUT"])
@jwt_required()
def toggle_schedule(schedule_id):
    """切换定时任务启用/禁用"""
    from app.models.ansible_job import AnsibleSchedule

    schedule = AnsibleSchedule.query.get(schedule_id)
    if not schedule:
        return error(msg="定时任务不存在")

    schedule.enabled = not schedule.enabled
    db.session.commit()

    return success(data={"id": schedule.id, "enabled": schedule.enabled})


@ansible_bp.route("/schedules/<int:schedule_id>/logs", methods=["GET"])
@jwt_required()
def get_schedule_logs(schedule_id):
    """获取定时任务执行历史"""
    from app.models.ansible_job import AnsibleScheduleLog

    page = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)

    q = AnsibleScheduleLog.query.filter_by(schedule_id=schedule_id)
    total = q.count()
    logs = q.order_by(AnsibleScheduleLog.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "status": log.status,
            "output": log.output,
            "errorMsg": log.error_msg,
            "duration": log.duration,
            "startedAt": log.started_at.strftime("%Y-%m-%d %H:%M:%S") if log.started_at else None,
        })

    return success(data={"total": total, "list": result})


@ansible_bp.route("/schedules/task-types", methods=["GET"])
@jwt_required()
def get_task_types():
    """获取内置任务类型列表"""
    types = [
        {"value": "command", "label": "SSH 命令", "description": "在目标主机上执行自定义命令"},
        {"value": "cmdb_update", "label": "CMDB 自动巡检", "description": "自动检测服务器状态、容器、端口，更新 CMDB"},
        {"value": "disk_check", "label": "磁盘检查", "description": "检查所有服务器磁盘使用率，筛选超 80% 分区"},
        {"value": "service_check", "label": "服务健康检查", "description": "检查 nginx/mysql/docker 等服务运行状态"},
    ]
    return success(data=types)
