import hashlib
import hmac
import json
import logging

from flask import jsonify, request

from utils.file_io import save_webhook_data

LOG = logging.getLogger(__name__)


def _valid_signature(data: dict, raw_body: bytes, signature: str, timestamp: str, secret: str) -> bool:
    """Validate the Oura HMAC over its documented JSON representation.

    Oura's example signs ``timestamp + JSON.stringify(body)``. Accepting the
    exact bytes as well handles equivalent valid JSON sent with whitespace.
    Both forms still require the application client secret.
    """
    if not signature or not timestamp:
        return False
    signature = signature.removeprefix("sha256=").upper()
    canonical_body = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    for body in {raw_body, canonical_body}:
        expected = hmac.new(
            secret.encode("utf-8"), timestamp.encode("utf-8") + body, hashlib.sha256
        ).hexdigest().upper()
        if hmac.compare_digest(expected, signature):
            return True
    return False

def register_webhook_routes(app, config):
    @app.route("/oura-webhook", methods=["GET", "POST"])
    def webhook():
        if request.method == "GET":
            if hmac.compare_digest(
                request.args.get("verification_token", ""), config["verification_token"]
            ):
                return jsonify({"challenge": request.args.get("challenge")}), 200
            return "Invalid verification token", 401

        raw_body = request.get_data(cache=True)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "invalid JSON"}), 400

        if not _valid_signature(
            data,
            raw_body,
            request.headers.get("x-oura-signature", ""),
            request.headers.get("x-oura-timestamp", ""),
            config["client_secret"],
        ):
            LOG.warning("Rejected webhook with an invalid signature")
            return jsonify({"status": "invalid signature"}), 401

        try:
            if save_webhook_data(data, config):
                return {"status": "success"}, 200
            return {"status": "preserved unmatched event"}, 202
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            LOG.exception("Could not store verified webhook")
            return jsonify({"status": "storage error"}), 500
