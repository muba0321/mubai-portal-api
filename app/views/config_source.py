"""
配置源管理 API
支持切换 Apollo / Local 配置源
"""
from flask import Blueprint
from app.utils.response import success, error
from app.utils.config_manager import get_config_status, get_apollo_client

config_source_bp = Blueprint("config_source", __name__, url_prefix="/api/v1/config-source")


@config_source_bp.route("/status", methods=["GET"])
def get_status():
    """获取配置源状态"""
    return success(data=get_config_status())


@config_source_bp.route("/switch", methods=["POST"])
def switch_source():
    """切换配置源"""
    from flask import request
    data = request.get_json()
    source = data.get("source", "").lower()

    if source not in ('apollo', 'local', 'fallback'):
        return error(msg="无效的配置源，支持: apollo, local, fallback", code="400")

    # 更新环境变量（当前进程有效）
    import os
    os.environ["CONFIG_SOURCE"] = source

    # 刷新 Apollo 缓存
    client = get_apollo_client()
    if client and source != 'local':
        client.refresh()

    return success(msg=f"配置源已切换为: {source}", data={"source": source})


@config_source_bp.route("/preview", methods=["GET"])
def preview_config():
    """预览当前配置源下的配置值（不暴露敏感信息）"""
    from app.utils.config_manager import get_config

    # 返回非敏感配置预览
    preview_keys = ['ai.model', 'ai.timeout', 'prometheus.url', 'grafana.url', 'redis.host', 'redis.port']
    result = {}
    for key in preview_keys:
        result[key] = get_config(key)

    # 敏感配置只显示是否存在
    sensitive_keys = ['database.url', 'ai.api_key', 'jwt.secret_key', 'secret_key']
    for key in sensitive_keys:
        value = get_config(key)
        result[key] = "***" if value else None

    return success(data=result)
