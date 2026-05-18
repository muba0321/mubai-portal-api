import logging
from flask import Flask, request
from app.config import config_map
from app.extensions import db, migrate, jwt, cors
from app.views import register_blueprints


def create_app(env="development"):
    app = Flask(__name__)
    app.config.from_object(config_map[env])

    # JWT 配置
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, supports_credentials=True)

    register_blueprints(app)

    # 确保管理员账号存在
    with app.app_context():
        from app.views.auth import _ensure_admin
        _ensure_admin()

    # 请求日志
    logger = logging.getLogger("sre-portal")
    logger.setLevel(logging.INFO)

    @app.before_request
    def log_request():
        logger.info(f"{request.method} {request.path}")

    # 健康检查
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "sre-portal-api"}

    # 统一错误处理
    @app.errorhandler(404)
    def not_found(e):
        return {"code": "40400", "data": None, "msg": "接口不存在"}, 404

    @app.errorhandler(500)
    def internal_error(e):
        return {"code": "50000", "data": None, "msg": "系统内部错误"}, 500

    return app
