import time
import os
import json
import requests
from config import load_config
from services.oura_api import register_webhook_subscription


def list_existing_webhooks(config, participant_id):
    token_path = os.path.join(config["data_dir"], "oura_tokens.json")
    with open(token_path, "r") as f:
        all_tokens = json.load(f)

    tokens = all_tokens.get(participant_id, {})
    access_token = tokens.get("access_token")
    if not access_token:
        return []

    resp = requests.get(
        "https://api.ouraring.com/v2/webhook/subscription",
        headers={
            "x-client-id": config["client_id"],
            "x-client-secret": config["client_secret"],
            "Content-Type": "application/json"
        }
    )

    if resp.status_code != 200:
        print(f"Failed to list existing webhooks: {resp.text}")
        return []

    return [wh["data_type"] for wh in resp.json()]

def register_all_webhooks(config, participant_id, retries=3):
    existing = list_existing_webhooks(config, participant_id)
    print(f"Existing webhooks: {existing}")

    failed = []
    for data_type in config["data_types"]:
        if data_type in existing:
            print(f"Skipping {data_type} (already registered)")
            continue

        print(f"Registering webhook for {data_type}...")
        status = register_webhook_subscription(
            config,
            participant_id=participant_id,
            data_type=data_type,
            event_type="update"
        )

        if status != 201:
            print(f"[{data_type}] Failed with status {status}. Will retry.")
            failed.append(data_type)
        time.sleep(1.5)  # small delay per OAuth/Ouraring API recs

    for attempt in range(1, retries + 1):
        if not failed:
            break
        print(f"\nRetry attempt {attempt} for failed subscriptions...")
        still_failed = []
        for data_type in failed:
            print(f"Retrying {data_type}...")
            status = register_webhook_subscription(
                config,
                participant_id=participant_id,
                data_type=data_type,
                event_type="update"
            )
            if status != 201:
                still_failed.append(data_type)
            time.sleep(1.5)
        failed = still_failed

    if failed:
        print(f"\nSome webhooks still failed after {retries} retries: {failed}")
    else:
        print("\nAll webhooks registered successfully.")

if __name__ == "__main__":
    config = load_config()
    participant_id = input("Enter participant ID to register all webhooks for: ").strip()
    if participant_id:
        register_all_webhooks(config=config, participant_id=participant_id)