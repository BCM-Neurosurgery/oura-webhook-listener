import os, json, requests
from datetime import datetime
from zoneinfo import ZoneInfo

def save_webhook_data(data, base_dir):
    user_id = data.get("user_id")
    data_type = data.get("data_type")

    if not user_id or not data_type:
        raise ValueError("Missing user_id or data_type in webhook event")

    # Paths
    map_path = os.path.normpath(os.path.join(base_dir, "..", "participant_map.json"))
    token_path = os.path.normpath(os.path.join(base_dir, "..", "oura_tokens.json"))
    
    # Load participant map
    user_map = {}
    if os.path.exists(map_path):
        with open(map_path, "r") as f:
            user_map = json.load(f)

    # If user_id not mapped yet, attempt to match from token entries
    if user_id not in user_map:
        with open(token_path, "r") as f:
            all_tokens = json.load(f)
        for participant_id, token_info in all_tokens.items():
            # Assume only one participant is authorized at a time
            if participant_id not in user_map.values():
                user_map[user_id] = participant_id
                with open(map_path, "w") as f:
                    json.dump(user_map, f, indent=2)
                print(f"[Mapping] Mapped user_id {user_id} → participant_id {participant_id}")
                break
        else:
            raise ValueError("Could not infer participant_id for user_id")

    participant_id = user_map[user_id]

    # Save webhook data
    timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%dT%H-%M-%S")
    save_path = os.path.join(base_dir, participant_id, data_type)
    os.makedirs(save_path, exist_ok=True)

    with open(os.path.join(save_path, f"{timestamp}.json"), "w") as f:
        json.dump(data, f, indent=2)

def send_webhook_signal(timestamp, path):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, f"{timestamp}.json"), "w") as f:
        json.dump({"event": "new_webhook", "timestamp": timestamp}, f, indent=2)