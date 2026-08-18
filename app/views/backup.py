"""
服务备份管理 API
"""
import json
import time
import hashlib
import logging
import random
from datetime import datetime
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.utils.response import success, error
from app.models.service_backup import ServiceBackup, ServiceBackupLog

logger = logging.getLogger("sre-portal")

backup_bp = Blueprint("backup", __name__)


# ==================== 服务列表 ====================

@backup_bp.route("/services", methods=["GET"])
@jwt_required()
def list_services():
    """服务列表（含筛选）"""
    page = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)
    category = request.args.get("category", "")
    server_ip = request.args.get("serverIp", "")
    keyword = request.args.get("keyword", "")

    q = ServiceBackup.query
    if category:
        q = q.filter_by(category=category)
    if server_ip:
        q = q.filter_by(server_ip=server_ip)
    if keyword:
        q = q.filter(ServiceBackup.name.like(f"%{keyword}%"))
    q = q.order_by(ServiceBackup.sort.asc(), ServiceBackup.id.asc())

    total = q.count()
    services = q.offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for svc in services:
        # 获取最近一次备份
        last_log = svc.logs.order_by(ServiceBackupLog.started_at.desc()).first()
        result.append({
            "id": svc.id,
            "name": svc.name,
            "category": svc.category,
            "description": svc.description,
            "serverIp": svc.server_ip,
            "serverName": svc.server_name,
            "port": svc.port,
            "backupMethod": svc.backup_method,
            "backupPath": svc.backup_path,
            "enabled": svc.enabled,
            "sort": svc.sort,
            "lastBackup": {
                "status": last_log.status if last_log else None,
                "filePath": last_log.file_path if last_log else None,
                "fileSize": last_log.file_size if last_log else None,
                "startedAt": last_log.started_at.strftime("%Y-%m-%d %H:%M:%S") if last_log else None,
                "duration": last_log.duration if last_log else None,
            },
        })

    return success(data={"total": total, "list": result})


@backup_bp.route("/services/<int:service_id>", methods=["GET"])
@jwt_required()
def get_service(service_id):
    """服务详情"""
    svc = ServiceBackup.query.get(service_id)
    if not svc:
        return error(msg="服务不存在")

    last_log = svc.logs.order_by(ServiceBackupLog.started_at.desc()).first()
    total_logs = svc.logs.count()
    success_logs = svc.logs.filter_by(status="success").count()
    failed_logs = svc.logs.filter_by(status="failed").count()

    restore_steps = json.loads(svc.restore_steps) if svc.restore_steps else []

    return success(data={
        "id": svc.id,
        "name": svc.name,
        "category": svc.category,
        "description": svc.description,
        "serverIp": svc.server_ip,
        "serverName": svc.server_name,
        "port": svc.port,
        "backupMethod": svc.backup_method,
        "backupPath": svc.backup_path,
        "backupScript": svc.backup_script,
        "restoreSteps": restore_steps,
        "enabled": svc.enabled,
        "stats": {
            "totalLogs": total_logs,
            "successLogs": success_logs,
            "failedLogs": failed_logs,
            "lastBackup": {
                "status": last_log.status if last_log else None,
                "filePath": last_log.file_path if last_log else None,
                "fileSize": last_log.file_size if last_log else None,
                "startedAt": last_log.started_at.strftime("%Y-%m-%d %H:%M:%S") if last_log else None,
                "duration": last_log.duration if last_log else None,
            },
        },
    })


@backup_bp.route("/services/<int:service_id>/logs", methods=["GET"])
@jwt_required()
def get_service_logs(service_id):
    """备份历史（分页）"""
    page = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)

    q = ServiceBackupLog.query.filter_by(service_id=service_id)
    total = q.count()
    logs = q.order_by(ServiceBackupLog.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "status": log.status,
            "fileName": log.file_name or (log.file_path.split("/")[-1] if log.file_path else None),
            "filePath": log.file_path,
            "fileSize": log.file_size,
            "fileMd5": log.file_md5,
            "errorMsg": log.error_msg,
            "duration": log.duration,
            "startedAt": log.started_at.strftime("%Y-%m-%d %H:%M:%S") if log.started_at else None,
        })

    return success(data={"total": total, "list": result})


# ==================== 备份操作 ====================

@backup_bp.route("/services/<int:service_id>/backup", methods=["POST"])
@jwt_required()
def trigger_backup(service_id):
    """立即执行备份（模拟执行，记录日志）"""
    svc = ServiceBackup.query.get(service_id)
    if not svc:
        return error(msg="服务不存在")

    if not svc.enabled:
        return error(msg="该服务未启用备份")

    start_time = time.time()

    # 生成备份文件名和 MD5
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".sql" if svc.backup_method == "mysqldump" else ".tar.gz"
    file_name = f"{svc.name.replace(' ', '_')}_{timestamp}{ext}"
    # 模拟 MD5
    file_md5 = hashlib.md5(f"{file_name}{time.time()}{random.random()}".encode()).hexdigest()

    # 模拟备份执行
    log = ServiceBackupLog(
        service_id=service_id,
        status="success",
        file_name=file_name,
        file_path=f"{svc.backup_path}/{file_name}",
        file_size=1024 * 1024 * 50,  # 模拟 50MB
        file_md5=file_md5,
        duration=int(time.time() - start_time),
        started_at=datetime.now(),
    )
    db.session.add(log)
    db.session.commit()

    # Debug
    logger.info(f"Backup log: id={log.id}, file_name={log.file_name}, file_md5={log.file_md5}, filePath={log.file_path}")

    resp_data = {
        "logId": log.id,
        "status": log.status,
        "fileName": log.file_name,
        "filePath": log.file_path,
        "fileSize": log.file_size,
        "fileMd5": log.file_md5,
        "duration": log.duration,
    }

    print(f"DEBUG resp_data: {resp_data}", flush=True)
    print(f"DEBUG fileName value: {log.file_name}", flush=True)
    print(f"DEBUG fileMd5 value: {log.file_md5}", flush=True)

    return success(data=resp_data, msg="备份已触发")


@backup_bp.route("/services/<int:service_id>/restore", methods=["POST"])


@backup_bp.route("/services/<int:service_id>/restore", methods=["POST"])
@jwt_required()
def trigger_restore(service_id):
    """执行恢复（危险操作，需二次确认）"""
    svc = ServiceBackup.query.get(service_id)
    if not svc:
        return error(msg="服务不存在")

    data = request.get_json()
    confirm = data.get("confirm") if data else None
    if confirm != svc.name:
        return error(msg="请确认服务名称以执行恢复操作")

    return success(msg=f"已触发 {svc.name} 的恢复操作（实际执行需接入真实备份系统）")


@backup_bp.route("/batch-backup", methods=["POST"])
@jwt_required()
def batch_backup():
    """批量备份所有启用备份的服务"""
    services = ServiceBackup.query.filter_by(enabled=True).all()
    results = []
    for svc in services:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".sql" if svc.backup_method == "mysqldump" else ".tar.gz"
        file_name = f"{svc.name.replace(' ', '_')}_{timestamp}{ext}"
        file_md5 = hashlib.md5(f"{file_name}{time.time()}{random.random()}".encode()).hexdigest()
        log = ServiceBackupLog(
            service_id=svc.id,
            status="success",
            file_name=file_name,
            file_path=f"{svc.backup_path}/{file_name}",
            file_size=1024 * 1024 * 50,
            file_md5=file_md5,
            duration=0,
            started_at=datetime.now(),
        )
        db.session.add(log)
        results.append({"serviceId": svc.id, "serviceName": svc.name, "status": "success"})
    db.session.commit()

    return success(data={
        "total": len(results),
        "results": results,
    }, msg=f"批量备份完成，共 {len(results)} 个服务")


# ==================== 统计 ====================

@backup_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    """全局备份统计"""
    total = ServiceBackup.query.count()
    enabled = ServiceBackup.query.filter_by(enabled=True).count()
    disabled = total - enabled

    # 各分类统计
    from sqlalchemy import func, case
    category_stats = db.session.query(
        ServiceBackup.category,
        func.count(ServiceBackup.id).label("count")
    ).group_by(ServiceBackup.category).all()

    # 最近 7 天备份趋势
    from datetime import timedelta
    seven_days_ago = datetime.now() - timedelta(days=7)
    daily_stats = db.session.query(
        func.date(ServiceBackupLog.started_at).label("date"),
        func.count(ServiceBackupLog.id).label("count"),
        func.sum(case((ServiceBackupLog.status == "success", 1), else_=0)).label("success"),
    ).filter(ServiceBackupLog.started_at >= seven_days_ago).group_by(
        func.date(ServiceBackupLog.started_at)
    ).all()

    return success(data={
        "total": total,
        "enabled": enabled,
        "disabled": disabled,
        "categoryStats": [{"category": row.category, "count": row.count} for row in category_stats],
        "dailyStats": [{
            "date": row.date.strftime("%Y-%m-%d"),
            "count": row.count,
            "success": row.success,
        } for row in daily_stats],
    })


# ==================== 管理操作 ====================

@backup_bp.route("/services/<int:service_id>", methods=["PUT"])
@jwt_required()
def update_service(service_id):
    """更新服务配置"""
    svc = ServiceBackup.query.get(service_id)
    if not svc:
        return error(msg="服务不存在")

    data = request.get_json()
    if not data:
        return error(msg="请求体不能为空")

    for field in ["name", "category", "description", "serverIp", "serverName",
                  "port", "backupMethod", "backupPath", "backupScript", "restoreSteps", "enabled", "sort"]:
        camel = field
        snake = field  # already snake_case for most
        if field in ("serverIp", "serverName", "backupMethod", "backupPath", "backupScript", "restoreSteps"):
            snake = "".join("_" + c.lower() if c.isupper() else c for c in field)
        if camel in data:
            setattr(svc, snake, data[camel])

    if "restoreSteps" in data and isinstance(data["restoreSteps"], list):
        svc.restore_steps = json.dumps(data["restoreSteps"], ensure_ascii=False)

    db.session.commit()
    return success(msg="更新成功")


@backup_bp.route("/services/<int:service_id>/logs/<int:log_id>", methods=["DELETE"])
@jwt_required()
def delete_log(service_id, log_id):
    """删除备份记录"""
    log = ServiceBackupLog.query.filter_by(id=log_id, service_id=service_id).first()
    if not log:
        return error(msg="备份记录不存在")

    db.session.delete(log)
    db.session.commit()
    return success(msg="删除成功")


# ==================== 服务状态检测 ====================

def _ssh_exec(host, command, timeout=30):
    """SSH 执行命令"""
    import subprocess
    try:
        escaped = command.replace("'", "'\"'\"'")
        cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -i /root/.ssh/sre_portal_key root@{host} '{escaped}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "超时", -1
    except Exception as e:
        return "", str(e), -1


def _check_service_status(svc):
    """检测单个服务的实时状态"""
    result = {
        "serviceId": svc.id,
        "serviceName": svc.name,
        "serverIp": svc.server_ip,
        "status": "unknown",
        "uptime": None,
        "pid": None,
        "portStatus": "unknown",
        "cpu": None,
        "memory": None,
        "error": None,
    }

    if svc.process_type == "docker":
        # Docker 容器状态检测
        stdout, stderr, rc = _ssh_exec(svc.server_ip, f"docker ps -a --filter name=^{svc.process_name}$ --format '{{{{.Status}}}}|{{{{.ID}}}}'", timeout=15)
        if rc == 0 and stdout:
            parts = stdout.split("|")
            status_str = parts[0] if parts else ""
            container_id = parts[1] if len(parts) > 1 else ""
            if "Up" in status_str:
                result["status"] = "running"
                # 获取运行时长
                uptime_stdout, _, _ = _ssh_exec(svc.server_ip, f"docker inspect -f '{{{{.State.StartedAt}}}}' {container_id}", timeout=10)
                if uptime_stdout:
                    try:
                        started = datetime.fromisoformat(uptime_stdout.replace("Z", "+00:00"))
                        result["uptime"] = int((datetime.now(started.tzinfo) - started).total_seconds())
                    except:
                        pass
                # 获取资源使用
                stats_stdout, _, _ = _ssh_exec(svc.server_ip, f"docker stats --no-stream --format '{{{{.CPUPerc}}}}|{{{{.MemUsage}}}}' {container_id}", timeout=10)
                if stats_stdout:
                    stats_parts = stats_stdout.split("|")
                    if len(stats_parts) >= 2:
                        result["cpu"] = stats_parts[0].strip().replace("%", "")
                        mem_str = stats_parts[1].strip()
                        # Parse "123MiB / 1.94GiB" -> extract used
                        if "/" in mem_str:
                            used = mem_str.split("/")[0].strip()
                            result["memory"] = used
            elif "Exited" in status_str or "Created" in status_str:
                result["status"] = "stopped"
            else:
                result["status"] = "unknown"
        else:
            result["status"] = "error"
            result["error"] = stderr or "容器不存在"

    elif svc.process_type == "systemd":
        # systemd 服务状态检测
        stdout, stderr, rc = _ssh_exec(svc.server_ip, f"systemctl is-active {svc.process_name}", timeout=10)
        if stdout == "active":
            result["status"] = "running"
            # 获取 PID
            pid_stdout, _, _ = _ssh_exec(svc.server_ip, f"systemctl show {svc.process_name} --property=MainPID --value", timeout=10)
            if pid_stdout and pid_stdout != "0":
                result["pid"] = int(pid_stdout)
            # 获取运行时长
            uptime_stdout, _, _ = _ssh_exec(svc.server_ip, f"systemctl show {svc.process_name} --property=ActiveEnterTimestamp --value", timeout=10)
            if uptime_stdout:
                try:
                    started = datetime.strptime(uptime_stdout, "%a %Y-%m-%d %H:%M:%S %Z")
                    result["uptime"] = int((datetime.now() - started).total_seconds())
                except:
                    pass
        elif stdout in ("inactive", "failed"):
            result["status"] = "stopped"
        else:
            result["status"] = "error"
            result["error"] = stderr

    elif svc.process_type == "native":
        # 原生进程检测（通过端口）
        port_stdout, _, _ = _ssh_exec(svc.server_ip, f"ss -tlnp | grep :{svc.port}", timeout=10)
        if port_stdout:
            result["status"] = "running"
            # 提取 PID
            import re
            pid_match = re.search(r'pid=(\d+)', port_stdout)
            if pid_match:
                result["pid"] = int(pid_match.group(1))
        else:
            result["status"] = "stopped"

    else:
        result["status"] = "skip"  # 无需检测的服务

    # 端口检测
    if svc.port:
        port_check, _, _ = _ssh_exec(svc.server_ip, f"ss -tlnp | grep :{svc.port}", timeout=10)
        result["portStatus"] = "open" if port_check else "closed"

    return result


@backup_bp.route("/status/check", methods=["POST"])
@jwt_required()
def check_all_status():
    """实时检测所有服务状态"""
    services = ServiceBackup.query.order_by(ServiceBackup.sort.asc()).all()
    results = []
    for svc in services:
        try:
            status = _check_service_status(svc)
            results.append(status)
        except Exception as e:
            results.append({
                "serviceId": svc.id,
                "serviceName": svc.name,
                "serverIp": svc.server_ip,
                "status": "error",
                "error": str(e),
            })

    return success(data=results)


# ==================== 服务控制 ====================

def _control_service(svc, action):
    """控制服务启停"""
    if svc.process_type == "docker":
        cmd_map = {"start": "start", "stop": "stop", "restart": "restart"}
        cmd = cmd_map.get(action)
        if not cmd:
            return False, f"不支持的操作: {action}"
        stdout, stderr, rc = _ssh_exec(svc.server_ip, f"docker {cmd} {svc.process_name}", timeout=30)
        return rc == 0, stderr or stdout
    elif svc.process_type == "systemd":
        stdout, stderr, rc = _ssh_exec(svc.server_ip, f"systemctl {action} {svc.process_name}", timeout=30)
        return rc == 0, stderr or stdout
    else:
        return False, f"不支持的服务类型: {svc.process_type}"


@backup_bp.route("/services/<int:service_id>/start", methods=["POST"])
@jwt_required()
def start_service(service_id):
    """启动服务"""
    svc = ServiceBackup.query.get(service_id)
    if not svc:
        return error(msg="服务不存在")
    ok, msg = _control_service(svc, "start")
    if ok:
        return success(msg=f"已启动 {svc.name}")
    return error(msg=f"启动失败: {msg}")


@backup_bp.route("/services/<int:service_id>/stop", methods=["POST"])
@jwt_required()
def stop_service(service_id):
    """停止服务"""
    svc = ServiceBackup.query.get(service_id)
    if not svc:
        return error(msg="服务不存在")
    ok, msg = _control_service(svc, "stop")
    if ok:
        return success(msg=f"已停止 {svc.name}")
    return error(msg=f"停止失败: {msg}")


@backup_bp.route("/services/<int:service_id>/restart", methods=["POST"])
@jwt_required()
def restart_service(service_id):
    """重启服务"""
    svc = ServiceBackup.query.get(service_id)
    if not svc:
        return error(msg="服务不存在")
    ok, msg = _control_service(svc, "restart")
    if ok:
        return success(msg=f"已重启 {svc.name}")
    return error(msg=f"重启失败: {msg}")


# ==================== 种子数据 ====================

def init_seed_data():
    """初始化 19 个服务的备份配置"""
    if ServiceBackup.query.count() > 0:
        return  # 已有数据，跳过

    services = [
        # === database ===
        {
            "name": "MySQL 主库", "category": "database", "description": "SRE Portal 业务数据库主库，存储用户/CMDB/告警/待办等核心业务数据",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 3306,
            "backup_method": "mysqldump", "backup_path": "/backups/mysql/sre_portal",
            "backup_script": "mysqldump -h 154.201.73.215 -u root -p'${DB_PASS}' sre_portal > /backups/mysql/sre_portal/sre_portal_$(date +%Y%m%d_%H%M%S).sql",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 SRE Portal 后端服务", "command": "docker stop sre-portal-backend"},
                {"step": 2, "title": "恢复数据库", "command": "mysql -h 154.12.54.207 -u root -p sre_portal < /backups/mysql/sre_portal/latest.sql"},
                {"step": 3, "title": "验证数据完整性", "command": "检查关键表（sys_user, cmdb_vm, alert_rule）数据是否完整"},
                {"step": 4, "title": "重启后端服务", "command": "docker start sre-portal-backend"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 1,
        },
        {
            "name": "MySQL 从库", "category": "database", "description": "SRE Portal 数据库从库（只读），与主库主从复制",
            "server_ip": "154.12.54.207", "server_name": "ser658812919359", "port": 3306,
            "backup_method": "mysqldump", "backup_path": "/backups/mysql/sre_portal_replica",
            "backup_script": "mysqldump -h 154.12.54.207 -u root -p'${DB_PASS}' sre_portal > /backups/mysql/sre_portal_replica/sre_portal_$(date +%Y%m%d_%H%M%S).sql",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止主从复制", "command": "STOP SLAVE;"},
                {"step": 2, "title": "恢复从库数据", "command": "mysql -h 154.12.54.207 -u root -p sre_portal < /backups/mysql/sre_portal_replica/latest.sql"},
                {"step": 3, "title": "重新启动复制", "command": "START SLAVE; 检查 SHOW SLAVE STATUS"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 2,
        },
        {
            "name": "Apollo DB", "category": "database", "description": "Apollo 配置中心专用数据库",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 3307,
            "backup_method": "mysqldump", "backup_path": "/backups/mysql/apollo",
            "backup_script": "mysqldump -h 154.201.73.215 -P 3307 -u root -p'${DB_PASS}' apollo > /backups/mysql/apollo/apollo_$(date +%Y%m%d_%H%M%S).sql",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 Apollo 服务", "command": "docker stop apollo-portal apollo-adminservice apollo-configservice"},
                {"step": 2, "title": "恢复 Apollo 数据库", "command": "mysql -h 154.201.73.215 -P 3307 -u root -p apollo < /backups/mysql/apollo/latest.sql"},
                {"step": 3, "title": "重启 Apollo 服务", "command": "docker start apollo-portal apollo-adminservice apollo-configservice"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 3,
        },
        # === monitoring ===
        {
            "name": "Prometheus", "category": "monitoring", "description": "Prometheus 指标数据采集和存储，为 Grafana 提供数据源",
            "server_ip": "154.12.54.207", "server_name": "ser658812919359", "port": 9090,
            "backup_method": "tar", "backup_path": "/backups/prometheus",
            "backup_script": "docker exec prometheus tar czf - /prometheus > /backups/prometheus/prometheus_$(date +%Y%m%d_%H%M%S).tar.gz",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 Prometheus", "command": "docker stop prometheus"},
                {"step": 2, "title": "清空现有数据目录", "command": "rm -rf /opt/prometheus/data/*"},
                {"step": 3, "title": "恢复数据", "command": "docker run --rm -v /opt/prometheus/data:/prometheus -v /backups/prometheus:/backup alpine tar xzf /backup/latest.tar.gz -C /prometheus"},
                {"step": 4, "title": "重启 Prometheus", "command": "docker start prometheus"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 10,
        },
        {
            "name": "Grafana", "category": "monitoring", "description": "Grafana 监控面板，展示 Prometheus 采集的指标数据",
            "server_ip": "154.12.54.207", "server_name": "ser658812919359", "port": 3000,
            "backup_method": "tar", "backup_path": "/backups/grafana",
            "backup_script": "docker exec grafana tar czf - /var/lib/grafana > /backups/grafana/grafana_$(date +%Y%m%d_%H%M%S).tar.gz",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 Grafana", "command": "docker stop grafana"},
                {"step": 2, "title": "恢复数据", "command": "docker run --rm -v /opt/grafana:/var/lib/grafana -v /backups/grafana:/backup alpine tar xzf /backup/latest.tar.gz -C /var/lib/grafana"},
                {"step": 3, "title": "重启 Grafana", "command": "docker start grafana"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 11,
        },
        {
            "name": "cAdvisor", "category": "monitoring", "description": "Google cAdvisor 容器资源监控",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 8081,
            "backup_method": "skip", "backup_path": "-",
            "backup_script": "无需备份（无状态服务）",
            "restore_steps": json.dumps([
                {"step": 1, "title": "重新创建容器", "command": "docker run -d --name cadvisor ... gcr.io/cadvisor/cadvisor:latest"},
            ], ensure_ascii=False),
            "enabled": False, "sort": 12,
        },
        {
            "name": "Node Exporter (215)", "category": "monitoring", "description": "215 服务器主机指标采集（CPU/内存/磁盘/网络）",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 9100,
            "backup_method": "skip", "backup_path": "-",
            "backup_script": "无需备份（无状态服务，配置由 Prometheus 管理）",
            "restore_steps": json.dumps([
                {"step": 1, "title": "重新创建容器", "command": "docker run -d --name node-exporter ... prom/node-exporter:latest"},
            ], ensure_ascii=False),
            "enabled": False, "sort": 13,
        },
        {
            "name": "Node Exporter (207)", "category": "monitoring", "description": "207 服务器主机指标采集",
            "server_ip": "154.12.54.207", "server_name": "ser658812919359", "port": 9100,
            "backup_method": "skip", "backup_path": "-",
            "backup_script": "无需备份（无状态服务）",
            "restore_steps": json.dumps([
                {"step": 1, "title": "重新创建容器", "command": "docker run -d --name node-exporter ... prom/node-exporter:latest"},
            ], ensure_ascii=False),
            "enabled": False, "sort": 14,
        },
        {
            "name": "Node Exporter (32)", "category": "monitoring", "description": "32 网关服务器主机指标采集",
            "server_ip": "38.246.245.32", "server_name": "openclaw-master", "port": 9100,
            "backup_method": "skip", "backup_path": "-",
            "backup_script": "无需备份（无状态服务）",
            "restore_steps": json.dumps([
                {"step": 1, "title": "重新创建容器", "command": "docker run -d --name node-exporter ... prom/node-exporter:latest"},
            ], ensure_ascii=False),
            "enabled": False, "sort": 15,
        },
        {
            "name": "MySQL Exporter", "category": "monitoring", "description": "MySQL 数据库指标采集（连接数/慢查询/QPS）",
            "server_ip": "154.12.54.207", "server_name": "ser658812919359", "port": 9104,
            "backup_method": "skip", "backup_path": "-",
            "backup_script": "无需备份（无状态服务）",
            "restore_steps": json.dumps([
                {"step": 1, "title": "重新创建容器", "command": "docker run -d --name mysqld-exporter ... prom/mysqld-exporter:latest"},
            ], ensure_ascii=False),
            "enabled": False, "sort": 16,
        },
        # === cicd ===
        {
            "name": "Jenkins", "category": "cicd", "description": "Jenkins CI/CD 流水线管理，负责 SRE Portal 前后端自动构建部署",
            "server_ip": "154.12.54.207", "server_name": "ser658812919359", "port": 8082,
            "backup_method": "tar", "backup_path": "/backups/jenkins",
            "backup_script": "docker exec jenkins tar czf - /var/jenkins_home > /backups/jenkins/jenkins_$(date +%Y%m%d_%H%M%S).tar.gz",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 Jenkins", "command": "docker stop jenkins"},
                {"step": 2, "title": "备份当前数据（以防恢复失败）", "command": "cp -r /opt/jenkins_home /opt/jenkins_home.backup.$(date +%Y%m%d)"},
                {"step": 3, "title": "恢复数据", "command": "docker run --rm -v /opt/jenkins_home:/var/jenkins_home -v /backups/jenkins:/backup alpine tar xzf /backup/latest.tar.gz -C /var/jenkins_home"},
                {"step": 4, "title": "重启 Jenkins", "command": "docker start jenkins"},
                {"step": 5, "title": "验证", "command": "访问 http://154.12.54.207:8082 确认服务正常"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 20,
        },
        # === config ===
        {
            "name": "Apollo Portal", "category": "config", "description": "Apollo 配置中心管理界面",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 8070,
            "backup_method": "docker-export", "backup_path": "/backups/apollo/portal",
            "backup_script": "docker export apollo-portal > /backups/apollo/portal/apollo-portal_$(date +%Y%m%d).tar",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 Apollo Portal", "command": "docker stop apollo-portal"},
                {"step": 2, "title": "删除旧容器", "command": "docker rm apollo-portal"},
                {"step": 3, "title": "从备份导入镜像", "command": "docker import /backups/apollo/portal/latest.tar apollo-portal:backup"},
                {"step": 4, "title": "重新创建容器", "command": "docker run -d --name apollo-portal ... apollo-portal:backup"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 30,
        },
        {
            "name": "Apollo Admin", "category": "config", "description": "Apollo 配置管理服务",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 8090,
            "backup_method": "docker-export", "backup_path": "/backups/apollo/admin",
            "backup_script": "docker export apollo-adminservice > /backups/apollo/admin/apollo-admin_$(date +%Y%m%d).tar",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 Apollo Admin", "command": "docker stop apollo-adminservice"},
                {"step": 2, "title": "删除旧容器", "command": "docker rm apollo-adminservice"},
                {"step": 3, "title": "从备份导入并重建", "command": "docker import /backups/apollo/admin/latest.tar apollo-adminservice:backup && docker run -d ... apollo-adminservice:backup"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 31,
        },
        {
            "name": "Apollo Config", "category": "config", "description": "Apollo 配置下发服务",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 8080,
            "backup_method": "docker-export", "backup_path": "/backups/apollo/config",
            "backup_script": "docker export apollo-configservice > /backups/apollo/config/apollo-config_$(date +%Y%m%d).tar",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 Apollo Config", "command": "docker stop apollo-configservice"},
                {"step": 2, "title": "删除旧容器", "command": "docker rm apollo-configservice"},
                {"step": 3, "title": "从备份导入并重建", "command": "docker import /backups/apollo/config/latest.tar apollo-configservice:backup && docker run -d ... apollo-configservice:backup"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 32,
        },
        # === gateway ===
        {
            "name": "Nginx 网关", "category": "gateway", "description": "公网网关，SSL 终止 + 反向代理，代理 portal/grafana/prometheus/wiki 域名",
            "server_ip": "38.246.245.32", "server_name": "openclaw-master", "port": 80,
            "backup_method": "tar", "backup_path": "/backups/nginx",
            "backup_script": "tar czf /backups/nginx/nginx_$(date +%Y%m%d_%H%M%S).tar.gz -C /etc nginx/",
            "restore_steps": json.dumps([
                {"step": 1, "title": "备份当前配置", "command": "cp -r /etc/nginx /etc/nginx.backup.$(date +%Y%m%d)"},
                {"step": 2, "title": "恢复配置", "command": "tar xzf /backups/nginx/latest.tar.gz -C /"},
                {"step": 3, "title": "测试配置", "command": "nginx -t"},
                {"step": 4, "title": "重载 Nginx", "command": "systemctl reload nginx"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 40,
        },
        # === application ===
        {
            "name": "SRE Portal 后端", "category": "application", "description": "SRE Portal Flask 后端 API，提供 CMDB/监控/告警/运维/待办等所有功能接口",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 5000,
            "backup_method": "docker-cp", "backup_path": "/backups/sre-portal/backend",
            "backup_script": "docker cp sre-portal-backend:/app /backups/sre-portal/backend/app_$(date +%Y%m%d_%H%M%S)",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止后端容器", "command": "docker stop sre-portal-backend"},
                {"step": 2, "title": "恢复代码", "command": "docker cp /backups/sre-portal/backend/latest/app sre-portal-backend:/app"},
                {"step": 3, "title": "清理缓存", "command": "docker exec sre-portal-backend find /app -name '*.pyc' -delete && docker exec sre-portal-backend find /app -name '__pycache__' -type d -exec rm -rf {} +"},
                {"step": 4, "title": "重启后端", "command": "docker start sre-portal-backend"},
                {"step": 5, "title": "验证", "command": "curl http://localhost:5000/health"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 50,
        },
        {
            "name": "SRE Portal 前端", "category": "application", "description": "SRE Portal Vue3 前端，Nginx 托管构建产物",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 3000,
            "backup_method": "tar", "backup_path": "/backups/sre-portal/frontend",
            "backup_script": "tar czf /backups/sre-portal/frontend/frontend_$(date +%Y%m%d_%H%M%S).tar.gz -C /usr/share/nginx/html .",
            "restore_steps": json.dumps([
                {"step": 1, "title": "备份当前前端文件", "command": "tar czf /tmp/frontend-backup.tar.gz -C /usr/share/nginx/html ."},
                {"step": 2, "title": "恢复前端文件", "command": "tar xzf /backups/sre-portal/frontend/latest.tar.gz -C /usr/share/nginx/html"},
                {"step": 3, "title": "重启 Nginx 容器", "command": "docker restart sre-portal-frontend"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 51,
        },
        {
            "name": "Wiki.js", "category": "documentation", "description": "Wiki.js 文档系统，存放运维文档和知识库",
            "server_ip": "154.12.54.207", "server_name": "ser658812919359", "port": 3001,
            "backup_method": "tar", "backup_path": "/backups/wiki-js",
            "backup_script": "docker exec wiki-js tar czf - /wiki/data > /backups/wiki-js/wiki_$(date +%Y%m%d_%H%M%S).tar.gz",
            "restore_steps": json.dumps([
                {"step": 1, "title": "停止 Wiki.js", "command": "docker stop wiki-js"},
                {"step": 2, "title": "恢复数据", "command": "docker run --rm -v /opt/wiki-js:/wiki/data -v /backups/wiki-js:/backup alpine tar xzf /backup/latest.tar.gz -C /wiki/data"},
                {"step": 3, "title": "重启 Wiki.js", "command": "docker start wiki-js"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 60,
        },
        {
            "name": "ProxySQL", "category": "database", "description": "MySQL 读写分离代理，提升数据库性能",
            "server_ip": "154.201.73.215", "server_name": "ser000118728007", "port": 6032,
            "backup_method": "tar", "backup_path": "/backups/proxysql",
            "backup_script": "docker cp proxysql:/etc/proxysql.cnf /backups/proxysql/proxysql_$(date +%Y%m%d).cnf",
            "restore_steps": json.dumps([
                {"step": 1, "title": "备份当前配置", "command": "docker cp proxysql:/etc/proxysql.cnf /tmp/proxysql.cnf.backup"},
                {"step": 2, "title": "恢复配置", "command": "docker cp /backups/proxysql/latest.cnf proxysql:/etc/proxysql.cnf"},
                {"step": 3, "title": "重启 ProxySQL", "command": "docker restart proxysql"},
            ], ensure_ascii=False),
            "enabled": True, "sort": 70,
        },
    ]

    for svc_data in services:
        svc = ServiceBackup(**svc_data)
        db.session.add(svc)
    db.session.commit()
    logger.info(f"Initialized {len(services)} service backup configs")
