from app.views.auth import auth_bp
from app.views.cmdb import cmdb_bp
from app.views.dashboard import dashboard_bp
from app.views.database import database_bp
from app.views.system import system_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(cmdb_bp, url_prefix="/api/v1/cmdb")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(database_bp, url_prefix="/api/v1/database")
    app.register_blueprint(system_bp, url_prefix="/api/v1")
