"""Verified webhook ingestion and project routing."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from flask import current_app, jsonify, request

from utils.file_io import read_json, save_payload

LOG = logging.getLogger(__name__)
HEARTBEAT = Path("/run/oura-listener/webhook.last")


def _signature_valid(
    raw_body: bytes,
    provided: str,
    timestamp: str,
    client_secret: str,
    canonical_body: bytes = b"",
) -> bool:
    if not provided or not timestamp:
        return False
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    provided = provided.upper()
    bodies = (raw_body, canonical_body) if canonical_body and canonical_body != raw_body else (raw_body,)
    for body in bodies:
        message = timestamp.encode() + body
        expected = hmac.new(client_secret.encode(), message, hashlib.sha256).hexdigest().upper()
        if hmac.compare_digest(expected, provided):
            return True
    return False


def _destination(config: dict, user_id: str, data_type: str) -> Optional[Tuple[Path, str]]:
    matches = []
    for project, values in config["projects"].items():
        try:
            mapping = read_json(values["participant_map"], {})
        except (OSError, ValueError):
            LOG.exception("Could not read participant map project=%s", project)
            continue
        if user_id in mapping:
            matches.append((Path(values["webhook_posts"]) / str(mapping[user_id]) / data_type, project))
    return matches[0] if len(matches) == 1 else None


def register_webhook_routes(app) -> None:
    @app.route("/oura-webhook", methods=["GET", "POST"])
    def webhook():
        config = current_app.config["OURA"]
        if request.method == "GET":
            valid = hmac.compare_digest(
                request.args.get("verification_token", ""), config["verification_token"]
            )
            if not valid:
                return "Invalid verification token", 401
            return jsonify(challenge=request.args.get("challenge")), 200

        raw_body = request.get_data(cache=True)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(status="invalid JSON"), 400
        signed_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        if not _signature_valid(
            raw_body,
            request.headers.get("x-oura-signature", ""),
            request.headers.get("x-oura-timestamp", ""),
            config["client_secret"],
            signed_body,
        ):
            LOG.warning("Rejected webhook with invalid signature")
            return jsonify(status="invalid signature"), 401

        user_id = payload.get("user_id")
        data_type = payload.get("data_type")
        if not user_id or not data_type:
            save_payload(config["unmatched_webhook_posts"], payload)
            HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
            HEARTBEAT.touch()
            return jsonify(status="preserved unmatched event"), 202

        destination = _destination(config, str(user_id), str(data_type))
        if destination is None:
            save_payload(config["unmatched_webhook_posts"], payload)
            HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
            HEARTBEAT.touch()
            LOG.error("Preserved webhook with unknown or ambiguous user mapping")
            return jsonify(status="preserved unmatched event"), 202

        path, project = destination
        save_payload(path, payload)
        HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT.touch()
        LOG.info("Saved webhook project=%s data_type=%s", project, data_type)
        return jsonify(status="success"), 200
