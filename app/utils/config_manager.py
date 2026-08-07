"""
配置源管理器
支持 Apollo / Local 两种配置源切换
"""
import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# 全局 Apollo 客户端（延迟初始化）
_apollo_client = None
_apollo_enabled = False


def get_apollo_client():
    """获取 Apollo 客户端（单例）"""
    global _apollo_client, _apollo_enabled

    if _apollo_client is not None:
        return _apollo_client

    _apollo_enabled = os.getenv("APOLLO_ENABLED", "false").lower() == "true"
    if not _apollo_enabled:
        return None

    try:
        from app.utils.apollo_client import ApolloClient
        _apollo_client = ApolloClient(
            app_id='sre-portal-app',
            config_server=os.getenv("APOLLO_META", "http://154.201.73.129:8080"),
            cluster='default',
            namespaces=['application', 'redis-config', 'logging-config']
        )
        logger.info(f"Apollo 客户端初始化成功: {_apollo_client.config_server}")
        return _apollo_client
    except Exception as e:
        logger.warning(f"Apollo 初始化失败: {e}")
        return None


def get_config_source():
    """获取当前配置源设置（从数据库或环境变量）"""
    # 优先从环境变量（启动时固定）
    env_source = os.getenv("CONFIG_SOURCE", "").lower()
    if env_source in ('apollo', 'local', 'fallback'):
        return env_source

    # 默认 fallback 模式
    return 'fallback'


def get_config(key, default=None, from_source=None):
    """
    统一配置获取函数
    优先级: Apollo > .env > 默认值
    """
    source = from_source or get_config_source()

    # === Apollo 模式 ===
    if source == 'apollo':
        client = get_apollo_client()
        if client:
            value = client.get(key)
            if value is not None:
                return value
            # Apollo 读不到，记录警告
            logger.warning(f"Apollo 配置不存在: {key}")
        else:
            logger.error("Apollo 未启用但配置源设置为 apollo")

    # === Local 模式 ===
    elif source == 'local':
        pass  # 跳过 Apollo，直接走 .env

    # === Fallback 模式（默认）===
    else:
        client = get_apollo_client()
        if client:
            value = client.get(key)
            if value is not None:
                return value

    # 降级：环境变量 (.env)
    env_key = key.replace('.', '_').upper()
    value = os.getenv(env_key)
    if value is not None:
        return value

    # 兼容旧的环境变量名
    legacy_map = {
        'database.url': 'DATABASE_URL',
        'ai.api_key': 'AI_API_KEY',
        'ai.model': 'AI_MODEL',
        'jwt.secret_key': 'JWT_SECRET_KEY',
        'secret_key': 'SECRET_KEY',
        'prometheus.url': 'PROMETHEUS_URL',
        'grafana.url': 'GRAFANA_URL',
        'grafana.api_key': 'GRAFANA_API_KEY',
        'redis.host': 'REDIS_HOST',
        'redis.port': 'REDIS_PORT',
    }
    if key in legacy_map:
        value = os.getenv(legacy_map[key])
        if value is not None:
            return value

    # 最终默认值
    return default


def get_config_status():
    """获取配置源状态信息"""
    client = get_apollo_client()
    apollo_connected = False
    apollo_config_count = 0

    if client:
        apollo_connected = client.is_connected()
        if apollo_connected:
            configs = client.get_all()
            apollo_config_count = len(configs)

    return {
        "current_source": get_config_source(),
        "apollo_enabled": _apollo_enabled,
        "apollo_connected": apollo_connected,
        "apollo_config_count": apollo_config_count,
        "apollo_server": client.config_server if client else None,
    }
