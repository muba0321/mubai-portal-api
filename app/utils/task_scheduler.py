"""
定时任务调度器
轻量级实现：线程 + 数据库轮询 + 简单 Cron 解析
无需额外依赖（不用 APScheduler）
"""
import threading
import time
import logging
import subprocess
import json
from datetime import datetime, timedelta

from app.utils.task_report import TaskReport, Issue

logger = logging.getLogger("sre-portal")

# SSH 密钥路径
SSH_KEY = "/root/.ssh/sre_portal_key"
SSH_TIMEOUT = 60
CONNECT_TIMEOUT = 10

# 磁盘阈值
DISK_WARNING_THRESHOLD = 80
DISK_CRITICAL_THRESHOLD = 90


class SimpleCron:
    """简单的 Cron 表达式解析器"""

    @staticmethod
    def match_field(value, field_str, max_val):
        """检查 value 是否匹配 cron 字段"""
        if field_str == "*":
            return True
        # 处理逗号分隔
        for part in field_str.split(","):
            part = part.strip()
            if "/" in part:
                # 步长: */5, 1-30/5
                range_part, step = part.split("/", 1)
                step = int(step)
                if range_part == "*":
                    start, end = 0, max_val
                elif "-" in range_part:
                    start, end = map(int, range_part.split("-", 1))
                else:
                    start, end = int(range_part), max_val
                if start <= value <= end and (value - start) % step == 0:
                    return True
            elif "-" in part:
                start, end = map(int, part.split("-", 1))
                if start <= value <= end:
                    return True
            else:
                if value == int(part):
                    return True
        return False

    @classmethod
    def should_run(cls, cron_expr, now=None):
        """判断当前时间是否应该执行"""
        if not now:
            now = datetime.now()
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return False
        minute, hour, day, month, dow = parts
        return (
            cls.match_field(now.minute, minute, 59)
            and cls.match_field(now.hour, hour, 23)
            and cls.match_field(now.day, day, 31)
            and cls.match_field(now.month, month, 12)
            and cls.match_field(now.weekday() + 1, dow, 7)  # cron: 1=Monday
        )


class BuiltinTasks:
    """内置任务处理器"""

    @staticmethod
    def _ssh_exec(hosts, command, timeout=SSH_TIMEOUT):
        """批量 SSH 执行"""
        results = {}
        for host in hosts:
            try:
                escaped = command.replace("'", "'\"'\"'")
                cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout={CONNECT_TIMEOUT} -o BatchMode=yes -i {SSH_KEY} root@{host} '{escaped}'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
                results[host] = {
                    "output": result.stdout,
                    "error": result.stderr.strip(),
                    "exit_code": result.returncode,
                    "status": "success" if result.returncode == 0 else "failed",
                }
            except subprocess.TimeoutExpired:
                results[host] = {"output": "", "error": f"超时 ({timeout}s)", "exit_code": -1, "status": "timeout"}
            except Exception as e:
                results[host] = {"output": "", "error": str(e), "exit_code": -1, "status": "error"}
        return results

    @staticmethod
    def _ssh_one(host, command, timeout=30):
        """单台主机 SSH 执行，返回 (stdout, stderr, returncode)"""
        try:
            escaped = command.replace("'", "'\"'\"'")
            cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout={CONNECT_TIMEOUT} -o BatchMode=yes -i {SSH_KEY} root@{host} '{escaped}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", f"超时 ({timeout}s)", -1
        except Exception as e:
            return "", str(e), -1

    @classmethod
    def cmdb_update(cls):
        """CMDB 自动巡检 — 结构化输出"""
        from app.models.cmdb_vm import CmdbVM
        from app.extensions import db

        vms = CmdbVM.query.filter_by(deleted=0).all()
        report = TaskReport(task_name="CMDB 自动巡检", task_type="cmdb_update")
        report.total_hosts = len(vms)
        raw_lines = []

        online_count = 0
        offline_count = 0
        changes = []

        for vm in vms:
            ip = vm.external_ip
            raw_lines.append(f"\n--- {vm.name} ({ip}) ---")
            try:
                # Ping 检测
                stdout, stderr, rc = cls._ssh_one(ip, "echo OK", timeout=15)
                online = rc == 0 and "OK" in stdout

                if not online:
                    report.details.append({
                        "host": ip, "name": vm.name, "status": "offline",
                        "containers": [], "ports": [], "disk_usage": "-", "memory_usage": "-",
                    })
                    raw_lines.append(f"  状态: 离线 (SSH 不可达)")
                    if vm.status == 1:
                        changes.append(f"{vm.name}: online → offline")
                    vm.status = 0
                    offline_count += 1

                    report.issues.append(Issue(
                        host=ip, level="critical",
                        title=f"主机 {vm.name} 离线",
                        expected="SSH 可达，主机在线",
                        actual="SSH 连接超时/被拒绝",
                        impact=f"该主机 ({vm.name}) 上运行的所有服务不可用",
                        suggestion="检查主机网络连通性、安全组策略或重启主机",
                    ))
                    continue

                # 收集信息
                docker_cmd = "docker ps --format '{{.Names}}|{{.Status}}' 2>/dev/null"
                port_cmd = "ss -tlnp 2>/dev/null | awk 'NR>1 {print $4}' | sort -u"
                disk_cmd = "df -h / | tail -1 | awk '{print $5}'"
                mem_cmd = "free | grep Mem | awk '{printf \"%.0f\", $3/$2*100}'"

                stdout_d, _, _ = cls._ssh_one(ip, docker_cmd, timeout=30)
                stdout_p, _, _ = cls._ssh_one(ip, port_cmd, timeout=15)
                stdout_dk, _, _ = cls._ssh_one(ip, disk_cmd, timeout=10)
                stdout_m, _, _ = cls._ssh_one(ip, mem_cmd, timeout=10)

                containers = [c.split("|")[0] for c in stdout_d.strip().split("\n") if "|" in c and "Up" in c]
                ports = sorted(set(p.split(":")[-1] for p in stdout_p.strip().split("\n") if p and p.split(":")[-1].isdigit()))
                disk = stdout_dk.strip()
                memory = stdout_m.strip()

                container_names = containers[:8]
                port_list = ports[:10]

                # 更新描述
                prefix = vm.description.split(" | 容器:")[0] if " | 容器:" in vm.description else (vm.description or vm.name)
                container_info = f" | 容器: {', '.join(container_names)}" if container_names else ""
                port_info = f" | 端口: {','.join(port_list)}" if port_list else ""
                disk_info = f" | 磁盘: {disk}" if disk else ""
                mem_info = f" | 内存: {memory}%" if memory else ""

                vm.description = prefix + container_info + port_info + disk_info + mem_info
                vm.status = 1
                online_count += 1

                # 检测状态变化
                if vm.status != 1 and getattr(vm, '_old_status', None) == 0:
                    changes.append(f"{vm.name}: offline → online")

                # 磁盘/内存告警
                if disk:
                    try:
                        usage = int(disk.replace("%", ""))
                        if usage >= DISK_CRITICAL_THRESHOLD:
                            report.issues.append(Issue(
                                host=ip, level="critical",
                                title=f"{vm.name} 磁盘使用率 {disk}",
                                expected=f"< {DISK_WARNING_THRESHOLD}%",
                                actual=disk,
                                impact="磁盘空间不足可能导致服务不可用",
                                suggestion="清理日志或扩容磁盘",
                            ))
                        elif usage >= DISK_WARNING_THRESHOLD:
                            report.issues.append(Issue(
                                host=ip, level="warning",
                                title=f"{vm.name} 磁盘使用率 {disk}",
                                expected=f"< {DISK_WARNING_THRESHOLD}%",
                                actual=disk,
                                impact="磁盘空间即将写满",
                                suggestion="关注磁盘增长趋势",
                            ))
                    except ValueError:
                        pass

                if memory:
                    try:
                        mem_usage = int(memory)
                        if mem_usage >= 90:
                            report.issues.append(Issue(
                                host=ip, level="warning",
                                title=f"{vm.name} 内存使用率 {memory}%",
                                expected="< 85%",
                                actual=f"{memory}%",
                                impact="内存使用率过高可能导致 OOM",
                                suggestion="检查是否有内存泄漏进程",
                            ))
                    except ValueError:
                        pass

                report.details.append({
                    "host": ip, "name": vm.name, "status": "online",
                    "containers": container_names,
                    "ports": port_list,
                    "disk_usage": disk or "-",
                    "memory_usage": (memory + "%") if memory else "-",
                })
                raw_lines.append(f"  状态: 在线 | 容器: {len(containers)} | 端口: {len(ports)} | 磁盘: {disk} | 内存: {memory}%")

            except Exception as e:
                report.details.append({
                    "host": ip, "name": vm.name, "status": "error",
                    "error": str(e),
                })
                raw_lines.append(f"  状态: 错误 ({e})")

        db.session.commit()

        report.summary = {
            "online": online_count,
            "offline": offline_count,
            "changes": changes,
        }
        report.raw_output = "\n".join(raw_lines)

        return report

    @classmethod
    def disk_check(cls):
        """磁盘使用率检查 — 结构化输出"""
        from app.models.cmdb_vm import CmdbVM

        vms = CmdbVM.query.filter_by(deleted=0, status=1).all()
        report = TaskReport(task_name="磁盘使用检查", task_type="disk_check")
        report.total_hosts = len(vms)
        raw_lines = []

        normal_count = 0
        warning_count = 0
        critical_count = 0
        error_count = 0

        for vm in vms:
            ip = vm.external_ip
            raw_lines.append(f"\n--- {vm.name} ({ip}) ---")
            try:
                cmd = ("df -h --output=source,size,used,avail,pcent,target 2>/dev/null | tail -n +2")
                stdout, stderr, rc = cls._ssh_one(ip, cmd, timeout=30)

                partitions = []
                for line in stdout.strip().split("\n"):
                    parts = line.split()
                    if len(parts) >= 6:
                        usage_str = parts[4].replace("%", "")
                        try:
                            usage = int(usage_str)
                        except ValueError:
                            usage = 0

                        if usage >= DISK_CRITICAL_THRESHOLD:
                            status = "critical"
                        elif usage >= DISK_WARNING_THRESHOLD:
                            status = "warning"
                        else:
                            status = "normal"

                        partition = {
                            "device": parts[0],
                            "size": parts[1],
                            "used": parts[2],
                            "avail": parts[3],
                            "usage": usage_str + "%",
                            "mount": parts[5],
                            "status": status,
                        }
                        partitions.append(partition)

                        if status == "critical":
                            report.issues.append(Issue(
                                host=ip, level="critical",
                                title=f"{vm.name} — {parts[5]} 使用率 {usage_str}%",
                                expected=f"< {DISK_WARNING_THRESHOLD}%",
                                actual=f"{usage_str}% ({parts[2]}/{parts[1]})",
                                impact="磁盘空间严重不足，可能导致服务不可用、数据库无法写入",
                                suggestion=f"立即清理 {parts[5]} 目录下的日志/临时文件，或扩容磁盘",
                            ))
                        elif status == "warning":
                            report.issues.append(Issue(
                                host=ip, level="warning",
                                title=f"{vm.name} — {parts[5]} 使用率 {usage_str}%",
                                expected=f"< {DISK_WARNING_THRESHOLD}%",
                                actual=f"{usage_str}% ({parts[2]}/{parts[1]})",
                                impact="磁盘空间即将写满，可能影响数据写入",
                                suggestion="清理过期数据或关注增长趋势",
                            ))

                if not partitions:
                    # 可能 df 输出格式不同，尝试传统格式
                    stdout2, _, rc2 = cls._ssh_one(ip, "df -h | grep -v tmpfs | grep -v devtmpfs", timeout=30)
                    for line in stdout2.strip().split("\n")[1:]:  # skip header
                        parts = line.split()
                        if len(parts) >= 6:
                            usage_str = parts[4].replace("%", "")
                            try:
                                usage = int(usage_str)
                            except ValueError:
                                usage = 0
                            status = "critical" if usage >= DISK_CRITICAL_THRESHOLD else ("warning" if usage >= DISK_WARNING_THRESHOLD else "normal")
                            partitions.append({
                                "device": parts[0], "size": parts[1], "used": parts[2],
                                "avail": parts[3], "usage": usage_str + "%",
                                "mount": parts[5], "status": status,
                            })

                # 统计该主机的最高状态
                host_status = "normal"
                for p in partitions:
                    if p["status"] == "critical":
                        host_status = "critical"
                    elif p["status"] == "warning" and host_status != "critical":
                        host_status = "warning"

                report.details.append({
                    "host": ip, "name": vm.name, "partitions": partitions,
                })
                partition_summary = ", ".join(f"{p['mount']}={p['usage']}" for p in partitions)
                raw_lines.append(f"  {partition_summary}")

            except Exception as e:
                report.details.append({
                    "host": ip, "name": vm.name, "status": "error",
                    "error": str(e),
                })
                raw_lines.append(f"  错误: {e}")

        # 汇总
        for d in report.details:
            if d.get("status") == "error":
                error_count += 1
            elif any(p["status"] == "critical" for p in d.get("partitions", [])):
                critical_count += 1
            elif any(p["status"] == "warning" for p in d.get("partitions", [])):
                warning_count += 1
            else:
                normal_count += 1

        report.summary = {
            "normal": normal_count,
            "warning": warning_count,
            "critical": critical_count,
            "error": error_count,
        }
        report.raw_output = "\n".join(raw_lines)

        return report

    @classmethod
    def service_check(cls):
        """服务健康检查 — 结构化输出"""
        from app.models.cmdb_vm import CmdbVM

        vms = CmdbVM.query.filter_by(deleted=0, status=1).all()
        report = TaskReport(task_name="服务健康检查", task_type="service_check")
        report.total_hosts = len(vms)
        raw_lines = []

        services_to_check = ["nginx", "mysql", "docker", "sshd"]
        healthy_count = 0
        partial_count = 0
        all_down_count = 0
        error_count = 0

        for vm in vms:
            ip = vm.external_ip
            raw_lines.append(f"\n--- {vm.name} ({ip}) ---")
            try:
                # 逐个检查服务
                services = []
                for svc in services_to_check:
                    stdout, stderr, rc = cls._ssh_one(ip, f"systemctl is-active {svc} 2>/dev/null", timeout=10)
                    status = stdout.strip()
                    pid_cmd = f"systemctl show {svc} --property=MainPID --value 2>/dev/null"
                    pid_out, _, _ = cls._ssh_one(ip, pid_cmd, timeout=10)
                    pid = pid_out.strip() or None

                    services.append({
                        "name": svc,
                        "status": status,
                        "pid": pid if pid and pid != "0" else None,
                    })
                    raw_lines.append(f"  {svc}: {status}")

                # 判断整体状态
                active_count = sum(1 for s in services if s["status"] == "active")
                if active_count == len(services):
                    overall = "healthy"
                    healthy_count += 1
                elif active_count == 0:
                    overall = "all_down"
                    all_down_count += 1

                    report.issues.append(Issue(
                        host=ip, level="critical",
                        title=f"{vm.name} 所有核心服务停止",
                        expected="nginx/mysql/docker/sshd 全部 active",
                        actual="全部 inactive/failed",
                        impact="该主机完全不可用，所有依赖该主机的服务中断",
                        suggestion="检查主机是否宕机，尝试 SSH 连接排查；如主机正常则逐个启动服务",
                    ))
                else:
                    overall = "partial"
                    partial_count += 1

                    # 找出异常服务
                    for svc in services:
                        if svc["status"] != "active":
                            report.issues.append(Issue(
                                host=ip, level="critical",
                                title=f"{vm.name} — {svc['name']} 服务停止",
                                expected="active (running)",
                                actual=f"{svc['status']}",
                                impact=f"{svc['name']} 服务不可用，影响依赖该服务的业务",
                                suggestion=f"执行 systemctl start {svc['name']} 恢复服务；检查 journalctl -u {svc['name']} 排查原因",
                            ))

                report.details.append({
                    "host": ip, "name": vm.name,
                    "services": services,
                    "overall": overall,
                })

            except Exception as e:
                report.details.append({
                    "host": ip, "name": vm.name, "status": "error",
                    "error": str(e),
                })
                raw_lines.append(f"  错误: {e}")
                error_count += 1

        report.summary = {
            "healthy": healthy_count,
            "partial": partial_count,
            "all_down": all_down_count,
            "error": error_count,
        }
        report.raw_output = "\n".join(raw_lines)

        return report


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self, app):
        self.app = app
        self.running = False
        self.thread = None
        self._last_load = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("TaskScheduler started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("TaskScheduler stopped")

    def _run_loop(self):
        last_minute = -1
        while self.running:
            now = datetime.now()
            current_minute = now.hour * 60 + now.minute

            # 每分钟检查一次
            if current_minute != last_minute:
                last_minute = current_minute
                try:
                    self._check_and_run(now)
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")

            time.sleep(10)  # 每 10 秒唤醒一次检查

    def _check_and_run(self, now):
        from app.models.ansible_job import AnsibleSchedule, AnsibleScheduleLog
        from app.extensions import db

        with self.app.app_context():
            schedules = AnsibleSchedule.query.filter_by(enabled=True).all()

            for schedule in schedules:
                if not schedule.cron_expression:
                    continue
                if not SimpleCron.should_run(schedule.cron_expression, now):
                    continue

                # 防止同一分钟内重复执行
                if schedule.last_run and (now - schedule.last_run).total_seconds() < 55:
                    continue

                logger.info(f"Running scheduled task: {schedule.name} ({schedule.task_type})")
                start_time = time.time()

                try:
                    output, status, error = self._execute_task(schedule)
                    duration = int(time.time() - start_time)

                    # 更新 schedule
                    schedule.last_run = now
                    schedule.last_status = status
                    db.session.commit()

                    # 记录日志
                    log = AnsibleScheduleLog(
                        schedule_id=schedule.id,
                        schedule_name=schedule.name,
                        task_type=schedule.task_type,
                        status=status,
                        output=str(output)[:5000] if output else None,
                        error_msg=error,
                        duration=duration,
                        started_at=now,
                    )
                    db.session.add(log)
                    db.session.commit()
                    logger.info(f"Task {schedule.name} completed: {status} ({duration}s)")

                except Exception as e:
                    logger.error(f"Task {schedule.name} failed: {e}")
                    schedule.last_status = "error"
                    db.session.commit()

    def _execute_task(self, schedule):
        """执行任务，返回 (output, status, error)"""
        task_type = schedule.task_type or "command"

        if task_type == "cmdb_update":
            report = BuiltinTasks.cmdb_update()
            critical_count = sum(1 for i in report.issues if i.level == "critical")
            warning_count = sum(1 for i in report.issues if i.level == "warning")
            if critical_count > 0:
                status = "warning"
            elif warning_count > 0:
                status = "success"
            else:
                status = "success"
            return report.to_json(), status, None

        elif task_type == "disk_check":
            report = BuiltinTasks.disk_check()
            critical_count = sum(1 for i in report.issues if i.level == "critical")
            warning_count = sum(1 for i in report.issues if i.level == "warning")
            if critical_count > 0:
                status = "warning"
            else:
                status = "success"
            return report.to_json(), status, None

        elif task_type == "service_check":
            report = BuiltinTasks.service_check()
            critical_count = sum(1 for i in report.issues if i.level == "critical")
            if critical_count > 0:
                status = "warning"
            else:
                status = "success"
            return report.to_json(), status, None

        elif task_type == "command":
            # 从 command 字段或关联 job 获取命令
            command = schedule.command
            if not command and schedule.job_id:
                from app.models.ansible_job import AnsibleJob
                job = AnsibleJob.query.get(schedule.job_id)
                if job:
                    command = job.module_args

            if not command:
                return None, "failed", "没有可执行的命令"

            # 获取目标主机
            hosts = []
            if schedule.job_id:
                from app.models.ansible_job import AnsibleJob
                job = AnsibleJob.query.get(schedule.job_id)
                if job and job.targets:
                    hosts = json.loads(job.targets)

            if not hosts:
                from app.models.cmdb_vm import CmdbVM
                vms = CmdbVM.query.filter_by(deleted=0, status=1).all()
                hosts = [vm.external_ip for vm in vms]

            results = BuiltinTasks._ssh_exec(hosts, command)
            success = sum(1 for r in results.values() if r["status"] == "success")
            status = "success" if success == len(hosts) else "partial"
            return json.dumps(results, ensure_ascii=False, default=str), status, None

        else:
            return None, "failed", f"未知任务类型: {task_type}"


# 全局调度器实例
scheduler = None


def init_scheduler(app):
    """初始化调度器"""
    global scheduler
    scheduler = TaskScheduler(app)
    scheduler.start()
    return scheduler
