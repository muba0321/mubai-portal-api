import os
from dotenv import load_dotenv

load_dotenv()

# 项目版本
APP_VERSION = "1.0.1"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://root:huanxin0321@154.12.54.207:3306/sre_portal"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-prod")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_EXPIRES", 3600))
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv("JWT_REFRESH_EXPIRES", 86400 * 7))

    # AI 模型配置（通义千问 DashScope）
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "qwen3.5-plus")

    # Prometheus 监控数据源
    PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://45.205.31.249:9090")

    # Grafana 面板管理
    GRAFANA_URL = os.getenv("GRAFANA_URL", "http://45.205.31.249:3000")
    GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY", "")


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
