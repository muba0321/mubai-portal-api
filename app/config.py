import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://root:huanxin0321@154.12.54.207:3306/sre_portal"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-prod")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_EXPIRES", 3600))
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv("JWT_REFRESH_EXPIRES", 86400 * 7))


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
