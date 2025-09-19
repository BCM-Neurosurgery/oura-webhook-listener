import os
import json
import requests
from datetime import datetime
from config import load_config


def refresh_tokens():

    config = load_config()
    token_path = os.path.join(config["data_dir"], "oura_tokens.json")
    print(f'Running refresh at {datetime.now()}')

    if not os.path.exists(token_path):
        print("No token file found.")
        return

    with open(token_path, "r") as f:
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
        with open(token_path, "w") as f:
            json.dump(all_tokens, f, indent=2)

if __name__ == "__main__":
    refresh_tokens()