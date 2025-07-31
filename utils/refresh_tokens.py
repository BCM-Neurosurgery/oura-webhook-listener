import os
import json
import requests
from datetime import datetime

BASE_DIR ='/home/ec2-user/oura_webhook_listener/' 
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
TOKEN_PATH = os.path.join(BASE_DIR, "oura_data", "oura_tokens.json")

def refresh_tokens():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    if not os.path.exists(TOKEN_PATH):
        print("No token file found.")
        return

    with open(TOKEN_PATH, "r") as f:
        all_tokens = json.load(f)

    updated = False

    for participant_id, tokens in all_tokens.items():
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            print(f"[{participant_id}] Missing refresh_token.")
            continue

        response = requests.post(
            "https://api.ouraring.com/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
            }
        )

        if response.status_code != 200:
            print(f"[{participant_id}] Failed to refresh token: {response.text}")
            continue

        new_tokens = response.json()
        tokens["access_token"] = new_tokens["access_token"]
        tokens["refresh_token"] = new_tokens.get("refresh_token", refresh_token)  # fallback
        tokens["expires_in"] = new_tokens["expires_in"]
        tokens["last_refreshed"] = datetime.now().isoformat()
        updated = True

        print(f"[{participant_id}] Token refreshed.")

    if updated:
        with open(TOKEN_PATH, "w") as f:
            json.dump(all_tokens, f, indent=2)

if __name__ == "__main__":
    refresh_tokens()