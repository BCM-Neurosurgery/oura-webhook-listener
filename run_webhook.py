from flask import Flask
from config import load_config
from routes.oauth import register_oauth_routes
from routes.webhook import register_webhook_routes

def create_app(config):
    app = Flask(__name__)
    register_oauth_routes(app, config)
    register_webhook_routes(app, config)
    return app

if __name__ == "__main__":
    config = load_config()
    app = create_app(config)

    # Start Flask server bound to all interfaces
    app.run(host="0.0.0.0", port=config["webhook_port"])