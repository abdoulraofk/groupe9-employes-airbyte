from flask import Flask, jsonify

from .db import close_pool, init_pool
from .routes.employes import bp as employes_bp
from .routes.meta import bp as meta_bp


def create_app():
    app = Flask(__name__)
    init_pool(app)

    app.register_blueprint(employes_bp, url_prefix="/api/v1")
    app.register_blueprint(meta_bp, url_prefix="/api/v1")

    @app.teardown_appcontext
    def _teardown(exc=None):
        pass

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="ressource introuvable"), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error=str(e.description) if hasattr(e, "description") else "requete invalide"), 400

    app.cli.command("close-pool")(lambda: close_pool())

    return app
