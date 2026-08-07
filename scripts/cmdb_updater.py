#!/usr/bin/env python3
"""
SRE Portal CMDB 自动更新脚本
每 30 分钟检查指定服务器的状态，更新 CMDB 记录
"""

import json
import requests
import subprocess
import logging
from datetime import datetime

# 配置
LOG_FILE = "/opt/scripts/cmdb-updater.log"
API_BASE = "http://localhost:5000/api/v1"
API_USER = "admin"
API_PASS = "admin123"

# 要监控的服务器
SERVERS = {
    "215": {
        "ip": "154.201.73.215",
        "name": "应用服务器 (Portal + Apollo)",
        "cmdb_id": 20,
        "description_prefix": "SRE Portal前端(3000) + 后端API(5000) + MySQL主库(3306) + Apollo全家桶(8070/8080/8090) + cAdvisor(8081) + ProxySQL + Node Exporter(9100)"
    },
    "207": {
        "ip": "154.12.54.207",
        "name": "监控服务器 (Prometheus + Grafana + Wiki)",
        "cmdb_id": 14,
        "description_prefix": "Prometheus(9090) + Grafana(3000) + Wiki.js(8080) + MySQL从库(3306) + MySQL Exporter(9104) + Node Exporter(9100) + Nginx(80) + Hermes AI(8081) + Rclone WebDAV"
    },
    "32": {
        "ip": "38.246.245.32",
        "name": "Nginx 网关 (SSL + 反向代理)",
        "cmdb_id": None,  # 需要查找
        "description_prefix": "Nginx SSL终止(80/443) + 反向代理(portal/grafana/prometheus/wiki) + Nginx stub_status(8080) + Node Exporter(9100) + Nginx Exporter(9113) + OpenClaw Dashboard(3000)"
    }
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_auth_token():
    """获取 API 认证 Token"""
    try:
        resp = requests.post(f"{API_BASE}/auth/login", json={
            "username": API_USER,
            "password": API_PASS
        }, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "00000":
                return data["data"]["accessToken"]
    except Exception as e:
        logger.error(f"获取 Token 失败: {e}")
    return None


def ssh_exec(ip, command, timeout=30):
    """通过 SSH 执行远程命令"""
    try:
        # 使用绝对路径，转义单引号
        escaped_cmd = command.replace("'", "'\"'\"'")
        cmd = f"/usr/bin/ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@{ip} '{escaped_cmd}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            logger.debug(f"SSH [{ip}] rc={result.returncode}: {result.stderr[:100]}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"SSH 连接超时: {ip}")
        return None
    except Exception as e:
        logger.error(f"SSH 执行失败 [{ip}]: {e}")
        return None


def check_server_status(ip):
    """检查服务器状态"""
    # 检查是否可达
    try:
        result = subprocess.run(f"/bin/ping -c 2 -W 2 {ip}", shell=True, capture_output=True)
        if result.returncode != 0:
            return {"online": False, "error": "Ping 不通"}
    except:
        return {"online": False, "error": "Ping 失败"}

    # 获取系统信息
    uptime = ssh_exec(ip, "uptime -p 2>/dev/null || uptime")
    load = ssh_exec(ip, "cat /proc/loadavg | awk '{print $1, $2, $3}'")

    # 获取磁盘使用率
    disk = ssh_exec(ip, "df -h / | tail -1 | awk '{print $5}'")

    # 获取内存使用率
    memory = ssh_exec(ip, "free | grep Mem | awk '{printf \"%.0f\", $3/$2 * 100}'")

    return {
        "online": True,
        "uptime": uptime,
        "load": load,
        "disk_usage": disk,
        "memory_usage": f"{memory}%" if memory else None
    }


def get_docker_containers(ip):
    """获取 Docker 容器列表"""
    output = ssh_exec(ip, "docker ps --format '{{.Names}}|{{.Status}}|{{.Ports}}' 2>/dev/null")
    if not output:
        return []

    containers = []
    for line in output.split('\n'):
        if '|' in line:
            parts = line.split('|')
            if len(parts) >= 2:
                containers.append({
                    "name": parts[0],
                    "status": parts[1],
                    "ports": parts[2] if len(parts) > 2 else ""
                })
    return containers


def get_listening_ports(ip):
    """获取监听端口"""
    output = ssh_exec(ip, "ss -tlnp 2>/dev/null | awk 'NR>1 {print $4}' | sort -u")
    if not output:
        return []

    ports = []
    for line in output.split('\n'):
        line = line.strip()
        if line and ':' in line:
            port = line.split(':')[-1]
            if port.isdigit():
                ports.append(int(port))
    return sorted(set(ports))


def update_cmdb_record(token, cmdb_id, server_info, containers, ports):
    """更新 CMDB 记录"""
    # 构建描述
    container_names = [c["name"] for c in containers if c.get("status", "").startswith("Up")]
    container_info = f" | 容器: {', '.join(container_names[:8])}" if container_names else ""

    port_info = f" | 端口: {','.join(map(str, ports[:10]))}" if ports else ""

    status_text = "✅ 在线" if server_info["online"] else "❌ 离线"
    disk_text = f" | 磁盘: {server_info.get('disk_usage', 'N/A')}" if server_info.get("disk_usage") else ""
    mem_text = f" | 内存: {server_info.get('memory_usage', 'N/A')}" if server_info.get("memory_usage") else ""

    new_description = server_info.get("description_prefix", "") + container_info + port_info

    # 查找 cmdb_id（如果未提供）
    if not cmdb_id:
        # 通过 IP 查找
        try:
            resp = requests.get(f"{API_BASE}/cmdb/vms", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for vm in data.get("data", {}).get("list", []):
                    if vm.get("externalIp") == server_info.get("ip"):
                        cmdb_id = vm["id"]
                        break
        except Exception as e:
            logger.error(f"查找 CMDB ID 失败: {e}")

    if not cmdb_id:
        logger.warning(f"未找到 CMDB ID，跳过更新")
        return False

    # 更新记录
    payload = {
        "name": server_info.get("name"),
        "status": 1 if server_info["online"] else 0,
        "description": new_description,
    }

    try:
        resp = requests.put(
            f"{API_BASE}/cmdb/vms/{cmdb_id}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "00000":
                logger.info(f"✅ 更新成功: {server_info['name']} ({status_text}{disk_text}{mem_text})")
                return True
            else:
                logger.error(f"更新失败: {data.get('msg')}")
        else:
            logger.error(f"HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"更新 CMDB 异常: {e}")

    return False


def main():
    logger.info("=" * 60)
    logger.info("开始 CMDB 自动更新")
    logger.info("=" * 60)

    # 获取 Token
    token = get_auth_token()
    if not token:
        logger.error("无法获取 API Token，退出")
        return

    results = []

    for key, server in SERVERS.items():
        logger.info(f"\n--- 检查 {server['name']} ({server['ip']}) ---")

        # 1. 检查服务器状态
        server_info = check_server_status(server["ip"])
        server_info["name"] = server["name"]
        server_info["description_prefix"] = server["description_prefix"]
        server_info["ip"] = server["ip"]

        if not server_info["online"]:
            logger.warning(f"❌ {server['name']} 离线")
            results.append({"server": server["name"], "online": False})
            # 仍然尝试更新 CMDB 标记为离线
            update_cmdb_record(token, server["cmdb_id"], server_info, [], [])
            continue

        # 2. 获取 Docker 容器
        containers = get_docker_containers(server["ip"])
        logger.info(f"   📦 Docker 容器: {len(containers)} 个")
        for c in containers:
            status_icon = "🟢" if "Up" in c.get("status", "") else "🔴"
            logger.info(f"      {status_icon} {c['name']} ({c['status'][:20]})")

        # 3. 获取监听端口
        ports = get_listening_ports(server["ip"])
        logger.info(f"   🔌 监听端口: {len(ports)} 个")

        # 4. 更新 CMDB
        success = update_cmdb_record(token, server["cmdb_id"], server_info, containers, ports)
        results.append({
            "server": server["name"],
            "online": True,
            "containers": len(containers),
            "ports": len(ports),
            "updated": success
        })

    # 汇总
    logger.info("\n" + "=" * 60)
    logger.info("更新完成汇总")
    logger.info("=" * 60)
    for r in results:
        status = "✅" if r.get("updated") or not r["online"] else "❌"
        online_text = "在线" if r["online"] else "离线"
        logger.info(f"{status} {r['server']}: {online_text}")

    logger.info(f"\n下次检查: 30 分钟后")


if __name__ == "__main__":
    main()
