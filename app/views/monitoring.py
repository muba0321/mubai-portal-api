import time
import requests
from datetime import datetime, timedelta
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.config import Config
from app.utils.response import success

monitoring_bp = Blueprint("monitoring", __name__)

# 北京时间偏移量
BEIJING_TZ = timedelta(hours=8)

PROMETHEUS_URL = Config.__dict__.get(
    "PROMETHEUS_URL",
    "http://154.12.54.207:9090",
)

# Prometheus instance label -> 服务器元数据
SERVER_META = {
    "154.201.73.215:9100": {"name": "应用服务器", "ip": "154.201.73.215", "os": "Ubuntu 22.04"},
    "154.12.54.207:9100": {"name": "监控服务器", "ip": "154.12.54.207", "os": "Ubuntu 22.04"},
    "38.246.245.32:9100": {"name": "Nginx 网关", "ip": "38.246.245.32", "os": "Ubuntu 22.04"},
}

# 服务映射
INSTANCE_SERVICES = {
    "154.201.73.215:9100": ["sre-portal-frontend", "sre-portal-backend", "sre-portal-mysql", "node-exporter", "cadvisor"],
    "154.12.54.207:9100": ["prometheus", "grafana", "mysql", "node-exporter", "mysql-exporter"],
    "38.246.245.32:9100": ["nginx", "node-exporter", "nginx-exporter"],
}


def _parse_time(t, default=None):
    """解析时间字符串为 Unix 时间戳"""
    if t is None:
        return default
    if isinstance(t, (int, float)):
        return str(int(t))
    if t == "now":
        return str(int(time.time()))
    if t.startswith("-"):
        # 解析 -24h, -7d 等
        val = t[1:]
        if val.endswith("h"):
            return str(int(time.time()) - int(val[:-1]) * 3600)
        elif val.endswith("d"):
            return str(int(time.time()) - int(val[:-1]) * 86400)
        elif val.endswith("m"):
            return str(int(time.time()) - int(val[:-1]) * 60)
    return str(int(time.time()))


def _prom_query(query, start=None, end=None, step=None):
    if start and end and step:
        url = f"{PROMETHEUS_URL}/api/v1/query_range"
        params = {"query": query, "start": _parse_time(start), "end": _parse_time(end), "step": step}
    else:
        url = f"{PROMETHEUS_URL}/api/v1/query"
        params = {"query": query}
    try:
        resp = requests.get(url, params=params, timeout=10)
        return resp.json().get("data", {})
    except Exception:
        return {}


def _extract_value(result, default=0):
    if not result or "result" not in result:
        return default
    results = result["result"]
    if not results:
        return default
    try:
        return float(results[0]["value"][1])
    except (ValueError, IndexError, TypeError):
        return default


def _to_echarts_series(data, name_map=None):
    series = []
    categories = []
    if not data or "result" not in data:
        return {"categories": [], "series": []}

    for item in data.get("result", []):
        instance = item.get("metric", {}).get("instance", "unknown")
        # 过滤掉非 node-exporter 实例
        if name_map and instance not in name_map:
            continue
        name = name_map.get(instance, {}).get("name", instance) if name_map else instance
        values = []
        for point in item.get("values", []):
            ts = point[0]
            val = point[1]
            try:
                values.append((float(ts), float(val)))
            except (ValueError, TypeError):
                continue
        if not categories and values:
            categories = [
                (datetime.utcfromtimestamp(ts) + BEIJING_TZ).strftime("%m-%d %H:%M")
                for ts, _ in values
            ]
        series.append({
            "name": name,
            "data": [v for _, v in values],
        })

    return {"categories": categories, "series": series}


def _query_by_instance(query_template):
    """按 SERVER_META 中的 instance 标签逐个查询"""
    results = {}
    for instance in SERVER_META:
        query = query_template.format(instance=instance)
        data = _prom_query(query)
        results[instance] = _extract_value(data)
    return results


# ========== 全局总览 ==========

@monitoring_bp.route("/summary")
@jwt_required()
def get_summary():
    up_data = _prom_query('up{job=~".*"}')
    targets = up_data.get("result", [])
    total_targets = len(targets)
    up_targets = sum(1 for t in targets if t.get("value") and float(t.get("value", [0, 0])[1]) == 1)
    server_online = sum(1 for t in targets
                        if t.get("metric", {}).get("instance") in SERVER_META
                        and t.get("value") and float(t.get("value", [0, 0])[1]) == 1)

    cpu_data = _prom_query('avg(100 - (rate(node_cpu_seconds_total{mode="idle"}[5m]) * 100))')
    avg_cpu = round(_extract_value(cpu_data), 1)

    mem_data = _prom_query('avg((1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100)')
    avg_mem = round(_extract_value(mem_data), 1)

    disk_data = _prom_query('avg((1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)')
    avg_disk = round(_extract_value(disk_data), 1)

    return success(data={
        "server_online": server_online,
        "total_targets": total_targets,
        "up_targets": up_targets,
        "down_targets": total_targets - up_targets,
        "avg_cpu": avg_cpu,
        "avg_memory": avg_mem,
        "avg_disk": avg_disk,
        "alert_count": 0,
    })


@monitoring_bp.route("/targets")
@jwt_required()
def get_targets():
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/targets", timeout=10)
        data = resp.json().get("data", {})
        active = data.get("activeTargets", [])
        result = []
        for t in active:
            result.append({
                "job": t.get("labels", {}).get("job", ""),
                "instance": t.get("labels", {}).get("instance", ""),
                "health": t.get("health", "unknown"),
                "last_error": t.get("lastError", ""),
            })
        return success(data=result)
    except Exception:
        return success(data=[])


# ========== 服务器维度 ==========

@monitoring_bp.route("/servers")
@jwt_required()
def get_servers():
    # 通过 Prometheus up 指标判断在线状态
    up_data = _prom_query('up{job="node-exporter"}')
    online_instances = set()
    for r in up_data.get("result", []):
        inst = r.get("metric", {}).get("instance", "")
        val = r.get("value", [0, "0"])[1] if r.get("value") else "0"
        if val == "1":
            online_instances.add(inst)

    servers = []
    for instance, meta in SERVER_META.items():
        cpu_vals = _query_by_instance('100 - (rate(node_cpu_seconds_total{{instance="{instance}",mode="idle"}}[5m]) * 100)')
        mem_vals = _query_by_instance('(1 - node_memory_MemAvailable_bytes{{instance="{instance}"}} / node_memory_MemTotal_bytes{{instance="{instance}"}}) * 100')
        disk_vals = _query_by_instance('(1 - node_filesystem_avail_bytes{{instance="{instance}",mountpoint="/"}} / node_filesystem_size_bytes{{instance="{instance}",mountpoint="/"}}) * 100')
        load_vals = _query_by_instance('node_load1{{instance="{instance}"}}')

        online = instance in online_instances

        servers.append({
            "name": meta["name"],
            "ip": meta["ip"],
            "os": meta["os"],
            "online": online,
            "cpu": round(cpu_vals.get(instance, 0), 1),
            "memory": round(mem_vals.get(instance, 0), 1),
            "disk": round(disk_vals.get(instance, 0), 1),
            "load": round(load_vals.get(instance, 0), 1),
            "services": INSTANCE_SERVICES.get(instance, []),
        })
    return success(data=servers)


@monitoring_bp.route("/metrics/cpu")
@jwt_required()
def get_cpu_metrics():
    step = request.args.get("step", "5m")
    range_h = int(request.args.get("range", 24))
    data = _prom_query(
        '100 - (rate(node_cpu_seconds_total{mode="idle"}[5m]) * 100)',
        start=f"-{range_h}h",
        end="now",
        step=step,
    )
    return success(data=_to_echarts_series(data, name_map=SERVER_META))


@monitoring_bp.route("/metrics/memory")
@jwt_required()
def get_memory_metrics():
    step = request.args.get("step", "5m")
    range_h = int(request.args.get("range", 24))
    data = _prom_query(
        '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100',
        start=f"-{range_h}h",
        end="now",
        step=step,
    )
    return success(data=_to_echarts_series(data, name_map=SERVER_META))


@monitoring_bp.route("/metrics/disk")
@jwt_required()
def get_disk_metrics():
    data = _prom_query('(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100')
    result = []
    if data and "result" in data:
        for item in data["result"]:
            instance = item.get("metric", {}).get("instance", "")
            if instance not in SERVER_META:
                continue
            label = SERVER_META[instance]["name"]
            value = round(_extract_value(item), 1)
            result.append({"server": label, "instance": instance, "usage": value})
    return success(data=result)


@monitoring_bp.route("/metrics/network")
@jwt_required()
def get_network_metrics():
    step = request.args.get("step", "5m")
    range_h = int(request.args.get("range", 24))
    data_rx = _prom_query(
        'rate(node_network_receive_bytes_total{device!="lo"}[5m])',
        start=f"-{range_h}h",
        end="now",
        step=step,
    )
    return success(data=_to_echarts_series(data_rx, name_map=SERVER_META))


# ========== 数据库维度 ==========

@monitoring_bp.route("/mysql")
@jwt_required()
def get_mysql_metrics():
    conn_data = _prom_query('mysql_global_status_threads_connected{instance="154.12.54.207:9104"}')
    connections = int(_extract_value(conn_data))

    qps_data = _prom_query('rate(mysql_global_status_queries{instance="154.12.54.207:9104"}[5m])')
    qps = round(_extract_value(qps_data), 1)

    slow_data = _prom_query('mysql_global_status_slow_queries{instance="154.12.54.207:9104"}')
    slow = int(_extract_value(slow_data))

    run_data = _prom_query('mysql_global_status_threads_running{instance="154.12.54.207:9104"}')
    running = int(_extract_value(run_data))

    max_conn_data = _prom_query('mysql_global_variables_max_connections{instance="154.12.54.207:9104"}')
    max_conn = int(_extract_value(max_conn_data, 151))

    uptime_data = _prom_query('mysql_global_status_uptime{instance="154.12.54.207:9104"}')
    uptime = int(_extract_value(uptime_data))

    return success(data={
        "connections": connections,
        "max_connections": max_conn,
        "qps": qps,
        "slow_queries": slow,
        "threads_running": running,
        "uptime_seconds": uptime,
    })


# ========== CI/CD 维度 ==========

@monitoring_bp.route("/jenkins")
@jwt_required()
def get_jenkins_metrics():
    running_data = _prom_query('jenkins_runs_running_total')
    running = int(_extract_value(running_data))

    queue_data = _prom_query('jenkins_queue_size_value')
    queue = int(_extract_value(queue_data))

    exec_total_data = _prom_query('jenkins_executors_total')
    exec_total = int(_extract_value(exec_total_data))

    exec_free_data = _prom_query('jenkins_executors_free')
    exec_free = int(_extract_value(exec_free_data))

    return success(data={
        "running_builds": running,
        "queue_size": queue,
        "executors_total": exec_total,
        "executors_free": exec_free,
        "executors_busy": max(0, exec_total - exec_free),
    })
