import os
import json
import requests

def register_webhook_subscription(config, participant_id, data_type="daily_activity", event_type="update"):
    token_path = os.path.join(config["data_dir"], "oura_tokens.json")
    if not os.path.exists(token_path):
        print("Token file not found. Please authorize first.")
        return
    
    with open(token_path, "r") as f:
        all_tokens = json.load(f)

    tokens = all_tokens.get(participant_id)
    if not tokens:
        print(f"No tokens found for participant ID: {participant_id}")
        return
    
    access_token = tokens.get("access_token")
    if not access_token:
        print("No access_token in token file.")
        return

    subscription_data = {
        "callback_url": f"{config['server_address']}/oura-webhook",
        "verification_token": config["verification_token"],
        "event_type": event_type,
        "data_type": data_type
    }

    response = requests.post(
        "https://api.ouraring.com/v2/webhook/subscription",
        headers={
            "x-client-id": config["client_id"],
            "x-client-secret": config["client_secret"],
            "Content-Type": "application/json"
        },
        json=subscription_data
    )

    print(" Webhook subscription response:")
    print("Status:", response.status_code)
    print("Response:", response.text)