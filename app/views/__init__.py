from app.views.auth import auth_bp
from app.views.cmdb import cmdb_bp
from app.views.dashboard import dashboard_bp
from app.views.database import database_bp
from app.views.setting import setting_bp
from app.views.system import system_bp
from app.views.todo import todo_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(cmdb_bp, url_prefix="/api/v1/cmdb")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(database_bp, url_prefix="/api/v1/database")
    app.register_blueprint(setting_bp, url_prefix="/api/v1/settings")
    app.register_blueprint(system_bp, url_prefix="/api/v1")
    app.register_blueprint(todo_bp, url_prefix="/api/v1/todo")
