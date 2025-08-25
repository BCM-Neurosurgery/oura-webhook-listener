from datetime import datetime

from flask import request, redirect
from urllib.parse import urlencode
import requests
import os, json

def register_oauth_routes(app, config):
    @app.route("/authorize")
    def authorize():
        participant_id = request.args.get("participant_id")
        if not participant_id:
            return "Missing participant ID", 400
        auth_params = {
            "client_id": config["client_id"],
            "redirect_uri": f"{config['server_address']}/callback",
            "response_type": "code",
            "scope": "daily heartrate workout session tag",
            "state": participant_id
        }
        return redirect(f"https://cloud.ouraring.com/oauth/authorize?{urlencode(auth_params)}")

    @app.route("/callback")
    def oauth_callback():
        code = request.args.get("code")
        participant_id = request.args.get("state")
        if not code or not participant_id:
            return "Missing code or participant id", 400

        resp = requests.post("https://api.ouraring.com/oauth/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": f"{config['server_address']}/callback"
        })

        if resp.status_code != 200:
            return f"Token exchange failed: {resp.text}", 400

        tokens = resp.json()
        tokens['participant_id'] = participant_id  # Store for reference
        tokens['created_at'] = datetime.now().isoformat()

        # Save token to file
        os.makedirs(config["data_dir"], exist_ok=True)
        tokens_path = os.path.join(config["data_dir"], "oura_tokens.json")
        if os.path.exists(tokens_path):
            all_tokens = json.load(open(tokens_path))
        else:
            all_tokens = {}

        all_tokens[participant_id] = tokens
        json.dump(all_tokens, open(tokens_path, "w"), indent=2)

        return f"Authorization complete for {participant_id}.", 200