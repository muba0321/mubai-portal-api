import os
from dotenv import load_dotenv

load_dotenv()

# 项目版本
APP_VERSION = "1.0.7"

# 导入配置管理器（延迟加载，避免循环依赖）
from app.utils.config_manager import get_config as _get_config


class Config:
    # === 启动时必须的配置（从 Apollo/.env 加载）===
    SECRET_KEY = _get_config('secret_key', 'dev-secret-key-change-in-prod')
    SQLALCHEMY_DATABASE_URI = _get_config(
        'database.url',
        'mysql+pymysql://root:huanxin0321@154.201.73.215:3306/sre_portal'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 数据库连接池配置（优化性能）
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,           # 连接池大小
        "pool_recycle": 3600,      # 连接回收时间（秒）
        "pool_pre_ping": True,     # 连接前检测有效性
        "pool_timeout": 30,        # 连接超时时间
    }

    JWT_SECRET_KEY = _get_config('jwt.secret_key', 'jwt-secret-key-change-in-prod')
    JWT_ACCESS_TOKEN_EXPIRES = int(_get_config('jwt.expires', 3600))
    JWT_REFRESH_TOKEN_EXPIRES = int(_get_config('jwt.refresh_expires', 86400 * 7))

    # AI 模型配置（通义千问 DashScope）
    AI_API_KEY = _get_config('ai.api_key', '')
    AI_MODEL = _get_config('ai.model', 'qwen3.6-plus')
    AI_TIMEOUT = int(_get_config('ai.timeout', 90))

    # Prometheus 监控数据源
    PROMETHEUS_URL = _get_config('prometheus.url', 'http://154.12.54.207:9090')

    # Grafana 面板管理
    GRAFANA_URL = _get_config('grafana.url', 'http://154.12.54.207:3000')
    GRAFANA_API_KEY = _get_config('grafana.api_key', '')

    # SSH 密钥路径（运维中心）
    SSH_KEY_PATH = _get_config('ansible.ssh_key_path', '/root/.ssh/sre_portal_key')

    # Redis 配置
    REDIS_HOST = _get_config('redis.host', '154.201.73.215')
    REDIS_PORT = int(_get_config('redis.port', 6379))
    REDIS_PASSWORD = _get_config('redis.password', '')
    REDIS_DB = int(_get_config('redis.database', 0))
    REDIS_TIMEOUT = int(_get_config('redis.timeout', 5000))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}

# Jenkins 配置
JENKINS_URL = "http://154.12.54.207:8082"
JENKINS_USERNAME = "admin"
JENKINS_TOKEN = "11c2b2b1adf7940191dfd1d258e4284912"
