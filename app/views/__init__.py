from app.views.auth import auth_bp
from app.views.user import user_bp
from app.views.incident import incident_bp
from app.views.service import service_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(user_bp, url_prefix="/api/users")
    app.register_blueprint(incident_bp, url_prefix="/api/incidents")
    app.register_blueprint(service_bp, url_prefix="/api/services")
