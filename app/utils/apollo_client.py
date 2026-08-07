"""
Apollo 配置客户端 - 纯 HTTP 方式，无需 Java 依赖
支持多命名空间、enc: 加密配置自动解密
"""
import os
import json
import logging
import base64
import requests

logger = logging.getLogger(__name__)


class ApolloClient:
    """Apollo HTTP 客户端"""

    def __init__(self, app_id, config_server, cluster='default', namespaces=None):
        self.app_id = app_id
        self.config_server = config_server.rstrip('/')
        self.cluster = cluster
        self.namespaces = namespaces or ['application']
        self._cache = {}
        self._initialized = False

    def _fetch_config(self):
        """从 Apollo 拉取所有命名空间的配置"""
        result = {}
        for namespace in self.namespaces:
            url = f"{self.config_server}/configs/{self.app_id}/{self.cluster}/{namespace}"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    # configurations 已经是 dict，不需要 json.loads
                    configs = data.get('configurations', {})
                    if isinstance(configs, str):
                        configs = json.loads(configs)
                    result.update(configs)
            except Exception as e:
                logger.warning(f"Apollo 拉取配置失败 [{namespace}]: {e}")
        return result

    def get(self, key, default=None):
        """获取单个配置值"""
        if not self._initialized:
            self._cache = self._fetch_config()
            self._initialized = True

        value = self._cache.get(key, default)

        # 自动解密 enc:base64 格式
        if isinstance(value, str) and value.startswith('enc:'):
            try:
                value = base64.b64decode(value[4:]).decode('utf-8')
            except Exception:
                logger.warning(f"Apollo 配置解密失败: {key}")

        return value

    def get_all(self):
        """获取所有配置"""
        if not self._initialized:
            self._cache = self._fetch_config()
            self._initialized = True
        return self._cache.copy()

    def refresh(self):
        """强制刷新配置"""
        self._cache = self._fetch_config()
        self._initialized = True
        logger.info(f"Apollo 配置已刷新，共 {len(self._cache)} 项")

    def is_connected(self):
        """检查 Apollo 连接状态"""
        try:
            url = f"{self.config_server}/services/config"
            resp = requests.get(url, timeout=3)
            return resp.status_code == 200
        except Exception:
            return False
