from flask import request, jsonify
from utils.file_io import save_webhook_data
import traceback

def register_webhook_routes(app, config):
    @app.route("/oura-webhook", methods=["GET", "POST"])
    def webhook():
        if request.method == "GET":
            if request.args.get("verification_token") == config["verification_token"]:
                return jsonify({"challenge": request.args.get("challenge")}), 200
            return "Invalid verification token", 401

        elif request.method == "POST":
            try:
                data = request.get_json(force=True)
                save_webhook_data(data, config["webhook_posts"])
                return {"status": "success"}, 200
            except Exception as e:
                print("[Webhook] Error handling webhook:")
                traceback.print_exc()
                return jsonify({"status": "error", "message": str(e)}), 500