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

logger = logging.getLogger("sre-portal")

# SSH 密钥路径
SSH_KEY = "/root/.ssh/sre_portal_key"
SSH_TIMEOUT = 60
CONNECT_TIMEOUT = 10


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

    @classmethod
    def cmdb_update(cls):
        """CMDB 自动巡检"""
        from app.models.cmdb_vm import CmdbVM
        from app.extensions import db

        vms = CmdbVM.query.filter_by(deleted=0).all()
        results = {}
        for vm in vms:
            ip = vm.external_ip
            try:
                # Ping 检测
                ping_cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -i {SSH_KEY} root@{ip} 'echo OK'"
                r = subprocess.run(ping_cmd, shell=True, capture_output=True, text=True, timeout=15)
                online = r.returncode == 0 and "OK" in r.stdout

                if not online:
                    results[ip] = {"status": "unreachable", "output": "", "error": "无法连接"}
                    vm.status = 0
                    continue

                # 收集信息
                docker_cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -i {SSH_KEY} root@{ip} \"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' 2>/dev/null\""
                port_cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -i {SSH_KEY} root@{ip} 'ss -tlnp 2>/dev/null | awk \"NR>1 {{print \\$4}}\" | sort -u'"
                disk_cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -i {SSH_KEY} root@{ip} 'df -h / | tail -1 | awk \"{{print \\$5}}\"'"
                mem_cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -i {SSH_KEY} root@{ip} 'free | grep Mem | awk \"{{printf \\\"%.0f\\\", \\$3/\\$2*100}}\"'"

                containers = subprocess.run(docker_cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip().split("\n")
                ports = subprocess.run(port_cmd, shell=True, capture_output=True, text=True, timeout=15).stdout.strip().split("\n")
                disk = subprocess.run(disk_cmd, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()
                memory = subprocess.run(mem_cmd, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()

                container_names = [c.split("|")[0] for c in containers if "|" in c and "Up" in c]
                port_list = sorted(set(p.split(":")[-1] for p in ports if p and p.split(":")[-1].isdigit()))

                # 更新描述
                prefix = vm.description.split(" | 容器:")[0] if " | 容器:" in vm.description else (vm.description or vm.name)
                container_info = f" | 容器: {', '.join(container_names[:8])}" if container_names else ""
                port_info = f" | 端口: {','.join(port_list[:10])}" if port_list else ""
                disk_info = f" | 磁盘: {disk}" if disk else ""
                mem_info = f" | 内存: {memory}%" if memory else ""

                vm.description = prefix + container_info + port_info + disk_info + mem_info
                vm.status = 1
                results[ip] = {"status": "success", "containers": len(container_names), "ports": len(port_list)}

            except Exception as e:
                results[ip] = {"status": "error", "error": str(e)}
                vm.status = 0

        db.session.commit()
        return {"hosts": len(vms), "results": results}

    @classmethod
    def disk_check(cls):
        """磁盘使用率检查"""
        from app.models.cmdb_vm import CmdbVM
        vms = CmdbVM.query.filter_by(deleted=0, status=1).all()
        hosts = [vm.external_ip for vm in vms]
        command = "df -h | awk 'NR==1 || $5+0 > 80'"
        results = cls._ssh_exec(hosts, command)
        return results

    @classmethod
    def service_check(cls):
        """服务健康检查"""
        from app.models.cmdb_vm import CmdbVM
        vms = CmdbVM.query.filter_by(deleted=0, status=1).all()
        results = {}
        for vm in vms:
            command = "systemctl is-active nginx mysql docker 2>/dev/null"
            r = cls._ssh_exec([vm.external_ip], command)
            results[vm.external_ip] = r.get(vm.external_ip, {})
        return results


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
            result = BuiltinTasks.cmdb_update()
            return json.dumps(result, ensure_ascii=False, default=str), "success", None

        elif task_type == "disk_check":
            result = BuiltinTasks.disk_check()
            return json.dumps(result, ensure_ascii=False, default=str), "success", None

        elif task_type == "service_check":
            result = BuiltinTasks.service_check()
            return json.dumps(result, ensure_ascii=False, default=str), "success", None

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
