import logging
from typing import Optional

from flask import Flask, jsonify

from config import load_config
from routes.oauth import register_oauth_routes
from routes.webhook import register_webhook_routes


def create_app(config: Optional[dict] = None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    app.config["OURA"] = config or load_config()
    register_oauth_routes(app)
    register_webhook_routes(app)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=app.config["OURA"]["webhook_port"])
