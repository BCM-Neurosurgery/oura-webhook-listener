"""Project-aware OAuth enrollment routes."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlencode

import requests
from flask import abort, current_app, redirect, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from utils.file_io import atomic_write_json, file_lock, read_json

LOG = logging.getLogger(__name__)
OAUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
PERSONAL_URL = "https://api.ouraring.com/v2/usercollection/personal_info"
SCOPES = "personal daily heartrate workout session tag spo2Daily"
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _serializer(config: dict) -> URLSafeTimedSerializer:
    secret = config.get("oauth_state_secret") or config["verification_token"]
    return URLSafeTimedSerializer(secret, salt="oura-oauth-state")


def _redirect_uri(config: dict, project: str) -> str:
    return f"{config['server_address'].rstrip('/')}/{project}/callback"


def _record_user(config: dict, project: str, participant_id: str, access_token: str) -> None:
    try:
        response = requests.get(
            PERSONAL_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        body = response.json() if response.status_code == 200 else {}
    except (requests.RequestException, ValueError):
        LOG.warning("Could not update participant map for project=%s", project)
        return
    user_id = body.get("id")
    if not user_id:
        LOG.warning("Oura personal_info omitted user id for project=%s", project)
        return
    map_path = config["projects"][project]["participant_map"]
    with file_lock(map_path):
        mapping = read_json(map_path, {})
        mapping[user_id] = participant_id
        atomic_write_json(map_path, mapping)


def register_oauth_routes(app) -> None:
    @app.get("/<project>/authorize")
    def authorize(project: str):
        config = current_app.config["OURA"]
        if project not in config["projects"]:
            abort(404)
        participant_id = request.args.get("participant_id", "")
        if not SAFE_ID.fullmatch(participant_id):
            return "Missing or invalid participant ID", 400
        state = _serializer(config).dumps({"project": project, "participant_id": participant_id})
        params = {
            "client_id": config["client_id"],
            "redirect_uri": _redirect_uri(config, project),
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
        }
        return redirect(f"{OAUTH_URL}?{urlencode(params)}")

    @app.get("/<project>/callback")
    def oauth_callback(project: str):
        config = current_app.config["OURA"]
        if project not in config["projects"]:
            abort(404)
        try:
            state = _serializer(config).loads(request.args.get("state", ""), max_age=3600)
        except SignatureExpired:
            return "Authorization link expired; start again.", 400
        except BadSignature:
            return "Invalid authorization state.", 400
        if state.get("project") != project:
            return "Authorization project mismatch.", 400
        code = request.args.get("code")
        participant_id = state.get("participant_id")
        if not code or not participant_id:
            return "Missing authorization code.", 400

        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "redirect_uri": _redirect_uri(config, project),
            },
            timeout=20,
        )
        if response.status_code != 200:
            LOG.error("OAuth token exchange failed project=%s status=%s", project, response.status_code)
            return "Token exchange failed; contact the study team.", 502

        tokens = response.json()
        tokens["participant_id"] = participant_id
        token_path = config["projects"][project]["token_file"]
        with file_lock(token_path):
            all_tokens = read_json(token_path, {})
            all_tokens[participant_id] = tokens
            atomic_write_json(token_path, all_tokens)
        _record_user(config, project, participant_id, tokens["access_token"])
        return f"Authorization complete for {participant_id}.", 200
