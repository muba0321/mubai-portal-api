import json
import sys
sys.path.insert(0, '/app')

from app import create_app
from app.extensions import db
from app.models.alerting import AlertMetric, AlertRule, NotificationChannel, AlertTemplate

def seed_data():
    system_metrics = [
        {"name": "cpu_usage", "display_name": "CPU 使用率", "group": "system", "promql": "100 - (avg by(instance) (rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)", "unit": "%"},
        {"name": "memory_usage", "display_name": "内存使用率", "group": "system", "promql": "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100", "unit": "%"},
        {"name": "disk_usage", "display_name": "磁盘使用率", "group": "system", "promql": "(1 - node_filesystem_avail_bytes{mountpoint='/'} / node_filesystem_size_bytes{mountpoint='/'}) * 100", "unit": "%"},
        {"name": "network_rx_bytes", "display_name": "网络接收速率", "group": "system", "promql": "rate(node_network_receive_bytes_total{device='eth0'}[5m])", "unit": "B/s"},
        {"name": "network_tx_bytes", "display_name": "网络发送速率", "group": "system", "promql": "rate(node_network_transmit_bytes_total{device='eth0'}[5m])", "unit": "B/s"},
        {"name": "load_5m", "display_name": "5分钟负载", "group": "system", "promql": "node_load5", "unit": ""},
    ]
    mysql_metrics = [
        {"name": "mysql_connections", "display_name": "MySQL 连接数", "group": "mysql", "promql": "mysql_global_status_threads_connected", "unit": "个"},
        {"name": "mysql_qps", "display_name": "MySQL QPS", "group": "mysql", "promql": "rate(mysql_global_status_questions[5m])", "unit": "次/s"},
        {"name": "mysql_slow_queries", "display_name": "慢查询数", "group": "mysql", "promql": "rate(mysql_global_status_slow_queries[5m])", "unit": "次/s"},
        {"name": "mysql_uptime", "display_name": "MySQL 运行时长", "group": "mysql", "promql": "mysql_global_status_uptime", "unit": "秒"},
        {"name": "mysql_threads_running", "display_name": "活跃线程数", "group": "mysql", "promql": "mysql_global_status_threads_running", "unit": "个"},
        {"name": "mysql_replication_lag", "display_name": "主从延迟", "group": "mysql", "promql": "mysql_slave_status_seconds_behind_master", "unit": "秒"},
    ]
    jenkins_metrics = [
        {"name": "jenkins_running_builds", "display_name": "运行中构建", "group": "jenkins", "promql": "jenkins_executor_queue_value", "unit": "个"},
        {"name": "jenkins_queue_size", "display_name": "队列大小", "group": "jenkins", "promql": "jenkins_queue_size_value", "unit": "个"},
        {"name": "jenkins_executors_total", "display_name": "执行器总数", "group": "jenkins", "promql": "jenkins_executor_total_count_value", "unit": "个"},
        {"name": "jenkins_build_fail_rate", "display_name": "构建失败率", "group": "jenkins", "promql": "rate(jenkins_builds_failed_total[1h]) / (rate(jenkins_builds_failed_total[1h]) + rate(jenkins_builds_succeeded_total[1h])) * 100", "unit": "%"},
    ]
    nginx_metrics = [
        {"name": "nginx_active_connections", "display_name": "Nginx 活跃连接", "group": "nginx", "promql": "nginx_connections_active", "unit": "个"},
        {"name": "nginx_requests_rate", "display_name": "Nginx 请求速率", "group": "nginx", "promql": "rate(nginx_http_requests_total[5m])", "unit": "次/s"},
        {"name": "nginx_5xx_rate", "display_name": "Nginx 5xx 错误率", "group": "nginx", "promql": "rate(nginx_http_status{code=~'5..'}[5m]) / rate(nginx_http_status[5m]) * 100", "unit": "%"},
    ]
    docker_metrics = [
        {"name": "docker_container_cpu", "display_name": "容器 CPU 使用率", "group": "docker", "promql": "rate(container_cpu_usage_seconds_total[5m]) * 100", "unit": "%"},
        {"name": "docker_container_memory", "display_name": "容器内存使用", "group": "docker", "promql": "container_memory_usage_bytes", "unit": "B"},
        {"name": "docker_container_restarts", "display_name": "容器重启次数", "group": "docker", "promql": "increase(container_restart_count[1h])", "unit": "次"},
    ]
    all_metrics = system_metrics + mysql_metrics + jenkins_metrics + nginx_metrics + docker_metrics

    for m in all_metrics:
        existing = AlertMetric.query.filter_by(name=m["name"]).first()
        if not existing:
            metric = AlertMetric(
                name=m["name"], display_name=m["display_name"], group=m["group"],
                promql=m["promql"], unit=m["unit"], source_type="builtin",
            )
            db.session.add(metric)

    templates = [
        {"name": "系统基础监控", "description": "CPU、内存、磁盘、网络、负载等基础系统指标监控", "group": "system", "metrics": system_metrics, "rules": [
            {"name": "CPU 使用率过高", "metric_name": "cpu_usage", "condition_operator": ">", "condition_value": 80, "condition_duration": 300, "severity": "P1"},
            {"name": "内存使用率过高", "metric_name": "memory_usage", "condition_operator": ">", "condition_value": 90, "condition_duration": 300, "severity": "P0"},
            {"name": "磁盘使用率过高", "metric_name": "disk_usage", "condition_operator": ">", "condition_value": 85, "condition_duration": 600, "severity": "P1"},
            {"name": "5分钟负载过高", "metric_name": "load_5m", "condition_operator": ">", "condition_value": 10, "condition_duration": 300, "severity": "P2"},
            {"name": "网络接收速率异常", "metric_name": "network_rx_bytes", "condition_operator": ">", "condition_value": 104857600, "condition_duration": 120, "severity": "P2"},
            {"name": "网络发送速率异常", "metric_name": "network_tx_bytes", "condition_operator": ">", "condition_value": 104857600, "condition_duration": 120, "severity": "P2"},
        ]},
        {"name": "MySQL 监控", "description": "MySQL 连接数、QPS、慢查询、主从延迟等指标监控", "group": "mysql", "metrics": mysql_metrics, "rules": [
            {"name": "MySQL 连接数过多", "metric_name": "mysql_connections", "condition_operator": ">", "condition_value": 500, "condition_duration": 60, "severity": "P1"},
            {"name": "慢查询频率过高", "metric_name": "mysql_slow_queries", "condition_operator": ">", "condition_value": 0.1, "condition_duration": 300, "severity": "P2"},
            {"name": "主从延迟过大", "metric_name": "mysql_replication_lag", "condition_operator": ">", "condition_value": 60, "condition_duration": 120, "severity": "P0"},
            {"name": "活跃线程过多", "metric_name": "mysql_threads_running", "condition_operator": ">", "condition_value": 100, "condition_duration": 60, "severity": "P1"},
            {"name": "MySQL QPS 过高", "metric_name": "mysql_qps", "condition_operator": ">", "condition_value": 5000, "condition_duration": 300, "severity": "P2"},
        ]},
        {"name": "Jenkins 监控", "description": "Jenkins 构建状态、队列、执行器等 CI/CD 指标监控", "group": "jenkins", "metrics": jenkins_metrics, "rules": [
            {"name": "构建失败率过高", "metric_name": "jenkins_build_fail_rate", "condition_operator": ">", "condition_value": 20, "condition_duration": 600, "severity": "P1"},
            {"name": "构建队列积压", "metric_name": "jenkins_queue_size", "condition_operator": ">", "condition_value": 10, "condition_duration": 300, "severity": "P2"},
            {"name": "执行器全部占用", "metric_name": "jenkins_executors_total", "condition_operator": "==", "condition_value": 0, "condition_duration": 0, "severity": "P1"},
            {"name": "运行中构建过多", "metric_name": "jenkins_running_builds", "condition_operator": ">", "condition_value": 20, "condition_duration": 600, "severity": "P2"},
        ]},
        {"name": "Nginx 监控", "description": "Nginx 连接数、请求速率、错误率等 Web 服务指标", "group": "nginx", "metrics": nginx_metrics, "rules": [
            {"name": "5xx 错误率过高", "metric_name": "nginx_5xx_rate", "condition_operator": ">", "condition_value": 5, "condition_duration": 120, "severity": "P0"},
            {"name": "活跃连接过多", "metric_name": "nginx_active_connections", "condition_operator": ">", "condition_value": 10000, "condition_duration": 300, "severity": "P1"},
            {"name": "请求速率异常", "metric_name": "nginx_requests_rate", "condition_operator": ">", "condition_value": 1000, "condition_duration": 120, "severity": "P2"},
        ]},
        {"name": "Docker 监控", "description": "Docker 容器 CPU、内存、重启等容器运行指标", "group": "docker", "metrics": docker_metrics, "rules": [
            {"name": "容器 CPU 过高", "metric_name": "docker_container_cpu", "condition_operator": ">", "condition_value": 90, "condition_duration": 300, "severity": "P1"},
            {"name": "容器内存过高", "metric_name": "docker_container_memory", "condition_operator": ">", "condition_value": 4294967296, "condition_duration": 300, "severity": "P1"},
            {"name": "容器频繁重启", "metric_name": "docker_container_restarts", "condition_operator": ">", "condition_value": 3, "condition_duration": 3600, "severity": "P0"},
        ]},
    ]

    for t in templates:
        existing = AlertTemplate.query.filter_by(name=t["name"], source_type="builtin").first()
        if not existing:
            template = AlertTemplate(
                name=t["name"], description=t["description"], group=t["group"],
                source_type="builtin", metric_count=len(t["metrics"]), rule_count=len(t["rules"]),
                metrics_def=json.dumps(t["metrics"]), rules_def=json.dumps(t["rules"]),
            )
            db.session.add(template)

    default_channels = [
        {"type": "dingtalk", "name": "默认钉钉通知", "webhook_url": "", "level_filter": "all", "silence_period": 300},
        {"type": "wecom", "name": "默认企业微信通知", "webhook_url": "", "level_filter": "all", "silence_period": 300},
        {"type": "email", "name": "默认邮件通知", "email_recipients": "", "level_filter": "P0,P1", "silence_period": 600},
    ]
    for c in default_channels:
        existing = NotificationChannel.query.filter_by(name=c["name"]).first()
        if not existing:
            channel = NotificationChannel(**c)
            db.session.add(channel)

    db.session.commit()
    print("种子数据初始化完成")

app = create_app("production")
with app.app_context():
    seed_data()
