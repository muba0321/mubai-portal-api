import logging
from flask import Flask, request
from app.config import config_map
from app.extensions import db, migrate, jwt, cors
from app.views import register_blueprints
from app.utils import settings_cache


def create_app(env="development"):
    app = Flask(__name__)
    app.config.from_object(config_map[env])

    # JWT 配置
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"

    db.init_app(app)

    # 加载系统配置到内存缓存
    with app.app_context():
        try:
            settings_cache.refresh(db.session)
        except Exception:
            pass
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, supports_credentials=True)

    register_blueprints(app)

    # 打印配置源信息
    logger = logging.getLogger("sre-portal")
    with app.app_context():
        try:
            from app.utils.config_manager import get_config_status
            status = get_config_status()
            logger.info(f"Config source: {status['current_source']}, "
                       f"Apollo: {'connected' if status['apollo_connected'] else 'disabled'}, "
                       f"configs: {status['apollo_config_count']}")
        except Exception as e:
            logger.debug(f"Config source info: {e}")
    with app.app_context():
        try:
            from app.views.auth import _ensure_admin
            _ensure_admin()
        except Exception:
            pass  # 表未创建时跳过，由 seed_rbac.py 初始化

    # 初始化服务备份种子数据
    with app.app_context():
        try:
            from app.views.backup import init_seed_data
            init_seed_data()
        except Exception:
            pass  # 表未创建时跳过

    # 请求日志
    logger = logging.getLogger("sre-portal")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)

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

    # 启动定时任务调度器
    try:
        from app.utils.task_scheduler import init_scheduler
        init_scheduler(app)
    except Exception as e:
        logger.warning(f"调度器启动失败: {e}")

    return app
