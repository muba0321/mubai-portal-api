from flask import Flask
from app.config import config_map
from app.extensions import db, migrate, jwt, cors
from app.views import register_blueprints


def create_app(env="development"):
    app = Flask(__name__)
    app.config.from_object(config_map[env])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, supports_credentials=True)

    register_blueprints(app)

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "sre-portal-api"}

    return app
