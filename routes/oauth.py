"""OAuth enrollment routes for the single-project listener."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import redirect, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from utils.file_io import atomic_write_json, file_lock, read_json

LOG = logging.getLogger(__name__)
OAUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
PERSONAL_INFO_URL = "https://api.ouraring.com/v2/usercollection/personal_info"
STATE_MAX_AGE_SECONDS = 3600


def _state_serializer(config):
    # A separate secret can be provided, but existing deployments remain
    # compatible when their random verification token is used as the fallback.
    return URLSafeTimedSerializer(
        config.get("oauth_state_secret") or config["verification_token"],
        salt="oura-oauth-state",
    )


def _record_participant_map(config, participant_id, access_token):
    """Record the Oura user ID only when the configured scope permits it.

    A conflicting existing mapping is never overwritten. ``None`` means that
    the deployment must map the verified user ID from quarantine manually.
    """
    if "personal" not in config.get("data_scopes", []):
        return None
    try:
        response = requests.get(
            PERSONAL_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        user_id = response.json().get("id") if response.status_code == 200 else None
    except (requests.RequestException, ValueError):
        LOG.warning("Could not retrieve the Oura user ID after authorization")
        return None
    if not user_id:
        LOG.warning("Oura did not return a user ID after authorization")
        return None

    map_path = Path(config["data_dir"]) / "participant_map.json"
    with file_lock(map_path):
        participant_map = read_json(map_path, {})
        existing = participant_map.get(str(user_id))
        participant_already_mapped = any(
            known_user_id != str(user_id) and known_participant_id == participant_id
            for known_user_id, known_participant_id in participant_map.items()
        )
        if (existing and existing != participant_id) or participant_already_mapped:
            return False
        participant_map[str(user_id)] = participant_id
        atomic_write_json(map_path, participant_map)
    return True

def register_oauth_routes(app, config):
    @app.route("/authorize")
    def authorize():
        participant_id = request.args.get("participant_id")
        if not participant_id:
            return "Missing participant ID", 400
        scope = " ".join(config["data_scopes"])
        auth_params = {
            "client_id": config["client_id"],
            "redirect_uri": f"{config['server_address']}/callback",
            "response_type": "code",
            "scope": scope,
            "state": _state_serializer(config).dumps({"participant_id": participant_id}),
        }
        return redirect(f"{OAUTH_URL}?{urlencode(auth_params)}")

    @app.route("/callback")
    def oauth_callback():
        code = request.args.get("code")
        try:
            state = _state_serializer(config).loads(
                request.args.get("state", ""), max_age=STATE_MAX_AGE_SECONDS
            )
        except SignatureExpired:
            return "Authorization link expired; start again.", 400
        except BadSignature:
            return "Invalid authorization state.", 400

        participant_id = state.get("participant_id") if isinstance(state, dict) else None
        if not code or not participant_id:
            return "Missing authorization code or participant ID.", 400

        try:
            response = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "redirect_uri": f"{config['server_address']}/callback",
                },
                timeout=20,
            )
        except requests.RequestException:
            LOG.exception("OAuth token exchange request failed")
            return "Token exchange failed; try again later.", 502
        if response.status_code != 200:
            LOG.error("OAuth token exchange failed with status %s", response.status_code)
            return "Token exchange failed; contact the study team.", 502
        try:
            tokens = response.json()
        except ValueError:
            LOG.error("OAuth token exchange returned invalid JSON")
            return "Token exchange failed; contact the study team.", 502
        if not tokens.get("access_token"):
            LOG.error("OAuth token exchange omitted an access token")
            return "Token exchange failed; contact the study team.", 502

        map_result = _record_participant_map(config, participant_id, tokens["access_token"])
        if map_result is False:
            LOG.error("Authorization attempted to replace an existing participant map")
            return "This Oura account is already mapped to another participant.", 409

        tokens["participant_id"] = participant_id
        tokens["created_at"] = datetime.now(timezone.utc).isoformat()
        token_path = Path(config["data_dir"]) / "oura_tokens.json"
        with file_lock(token_path):
            all_tokens = read_json(token_path, {})
            all_tokens[participant_id] = tokens
            atomic_write_json(token_path, all_tokens)

        return "Authorization complete.", 200
