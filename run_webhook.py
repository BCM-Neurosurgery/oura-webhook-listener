from flask import Flask
from config import load_config
from routes.oauth import register_oauth_routes
from routes.webhook import register_webhook_routes


def create_app(config):
    flask_app = Flask(__name__)
    register_oauth_routes(flask_app, config)
    register_webhook_routes(flask_app, config)
    return flask_app


config = load_config()
app = create_app(config)

if __name__ == "__main__":
    # Start Flask server bound to all interfaces
    app.run(host="0.0.0.0", port=config["webhook_port"])