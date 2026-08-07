"""
SSH 远程命令执行引擎
使用 subprocess + SSH 密钥认证，无需额外依赖
"""
import subprocess
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger("sre-portal")

# SSH 密钥路径（从配置读取，默认值）
DEFAULT_SSH_KEY = "/root/.ssh/sre_portal_key"
SSH_TIMEOUT = 30
CONNECT_TIMEOUT = 10


class SSHRunner:
    """SSH 远程命令执行器"""

    def __init__(self, key_file=None, timeout=SSH_TIMEOUT):
        self.key_file = key_file or DEFAULT_SSH_KEY
        self.timeout = timeout

    def exec_on_host(self, host, command, user="root", timeout=None):
        """在单台主机上执行命令"""
        timeout = timeout or self.timeout
        try:
            cmd = (
                f"/usr/bin/ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout={CONNECT_TIMEOUT} "
                f"-o BatchMode=yes "
                f"-i {self.key_file} "
                f"{user}@{host} '{self._escape(command)}'"
            )
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=timeout
            )
            output = result.stdout
            error = result.stderr
            exit_code = result.returncode

            # 判断状态
            if exit_code == 0:
                status = "success"
            elif "Permission denied" in error or "Could not resolve hostname" in error:
                status = "unreachable"
            else:
                status = "failed"

            return {
                "host": host,
                "output": output,
                "error": error.strip() if error else "",
                "exit_code": exit_code,
                "status": status,
            }
        except subprocess.TimeoutExpired:
            return {
                "host": host,
                "output": "",
                "error": f"命令执行超时 ({timeout}s)",
                "exit_code": -1,
                "status": "timeout",
            }
        except Exception as e:
            return {
                "host": host,
                "output": "",
                "error": str(e),
                "exit_code": -1,
                "status": "error",
            }

    def exec_batch(self, hosts, command, max_workers=5, timeout=None):
        """批量在多台主机上执行命令"""
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.exec_on_host, h, command, timeout=timeout): h
                for h in hosts
            }
            for future in as_completed(futures):
                host = futures[future]
                results[host] = future.result()
        return results

    def ping_host(self, host, timeout=5):
        """快速检测主机是否可达"""
        try:
            cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout={timeout} -o BatchMode=yes -i {self.key_file} root@{host} 'echo OK'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout + 5)
            return result.returncode == 0 and "OK" in result.stdout
        except:
            return False

    @staticmethod
    def _escape(command):
        """转义命令中的单引号"""
        return command.replace("'", "'\"'\"'")

    @staticmethod
    def replace_variables(command, variables=None):
        """替换命令中的变量"""
        if not variables:
            return command

        # 内置变量
        now = datetime.now()
        builtins = {
            "date": now.strftime("%Y-%m-%d"),
            "datetime": now.strftime("%Y%m%d_%H%M%S"),
            "timestamp": str(int(now.timestamp())),
        }
        builtins.update(variables)

        for key, value in builtins.items():
            command = command.replace(f"{{{key}}}", str(value))

        return command

    @staticmethod
    def validate_command(command):
        """命令安全检查，阻止危险命令"""
        dangerous_patterns = [
            r'\brm\s+-rf\s+/\b',
            r'\brm\s+-rf\s+\*\s*$',
            r':\(\)\s*\{\s*:\|:\s*&\s*\}\s*;',  # fork bomb
            r'\bdd\s+if=/dev/zero\s+of=/dev/',
            r'\bmkfs\.',
            r'\bchmod\s+-R\s+777\s+/\b',
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                return False, f"检测到危险命令模式: {pattern}"
        return True, "OK"
