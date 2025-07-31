import json
import os

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")

    with open(config_path, "r") as f:
        config = json.load(f)

    # Expand any relative paths based on the script's directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config["data_dir"] = os.path.join(base_dir, config.get("data_dir", "oura_data"))
    config["webhook_posts"] = os.path.join(base_dir, config.get("webhook_posts", "oura_data/webhook_posts"))

    return config