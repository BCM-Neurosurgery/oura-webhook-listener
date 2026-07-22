"""Load non-secret JSON configuration and secrets from the environment."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

REQUIRED_ENV = ("OURA_CLIENT_ID", "OURA_CLIENT_SECRET", "OURA_VERIFICATION_TOKEN")
FORBIDDEN_JSON_KEYS = {"client_id", "client_secret", "verification_token", "slack_webhook_url"}


def load_config(path: Optional[str] = None) -> dict:
    config_path = Path(path or os.environ.get("OURA_CONFIG", Path(__file__).with_name("config.json")))
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)

    stale = FORBIDDEN_JSON_KEYS.intersection(config)
    if stale:
        raise ValueError(f"Remove secret keys from {config_path}: {', '.join(sorted(stale))}")

    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    config.update(
        client_id=os.environ["OURA_CLIENT_ID"],
        client_secret=os.environ["OURA_CLIENT_SECRET"],
        verification_token=os.environ["OURA_VERIFICATION_TOKEN"],
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL"),
        oauth_state_secret=os.environ.get("OAUTH_STATE_SECRET"),
    )
    config.setdefault("server_address", "https://ouralisten.bcmelias.com")
    config.setdefault("webhook_path", "/oura-webhook")
    config.setdefault("webhook_port", 5000)
    config.setdefault(
        "unmatched_webhook_posts",
        "/home/ec2-user/oura_webhook_listener/oura_data/unmatched_webhook_posts",
    )
    projects = config.get("projects")
    if not isinstance(projects, dict) or not projects:
        raise ValueError("config.json must contain a non-empty projects object")
    for project, values in projects.items():
        missing_keys = {"token_file", "participant_map", "webhook_posts"} - set(values)
        if missing_keys:
            raise ValueError(f"Project {project} is missing: {', '.join(sorted(missing_keys))}")
    return config


def callback_url(config: dict) -> str:
    return f"{config['server_address'].rstrip('/')}{config['webhook_path']}"
