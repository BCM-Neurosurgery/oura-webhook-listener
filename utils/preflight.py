"""Read-only checks for project routing and existing storage files."""

from __future__ import annotations

import os
from pathlib import Path

from config import load_config
from utils.file_io import read_json


def main() -> int:
    config = load_config()
    failures = []
    seen_users = {}
    print("Project OAuth and storage routing:")
    for name, project in config["projects"].items():
        token_path = Path(project["token_file"])
        map_path = Path(project["participant_map"])
        try:
            tokens = read_json(token_path, None)
        except (OSError, ValueError):
            tokens = None
        try:
            mapping = read_json(map_path, None)
        except (OSError, ValueError):
            mapping = None
        token_count = len(tokens) if isinstance(tokens, dict) else 0
        map_count = len(mapping) if isinstance(mapping, dict) else 0
        mapped_participants = set(mapping.values()) if isinstance(mapping, dict) else set()
        mapped_token_count = (
            sum(participant_id in mapped_participants for participant_id in tokens)
            if isinstance(tokens, dict)
            else 0
        )
        print(f"\n{name.upper()}")
        print(f"  authorize: {config['server_address']}/{name}/authorize")
        print(f"  callback:  {config['server_address']}/{name}/callback")
        print(f"  tokens:    {token_path} ({token_count} records)")
        print(f"  map:       {map_path} ({map_count} records)")
        print(f"  coverage:  {mapped_token_count}/{token_count} token records mapped")
        print(f"  posts:     {project['webhook_posts']}")
        if not isinstance(tokens, dict):
            failures.append(f"{name}: token file missing or invalid")
        if not isinstance(mapping, dict):
            failures.append(f"{name}: participant map missing or invalid")
            mapping = {}
        for user_id in mapping:
            if user_id in seen_users:
                failures.append(f"Oura user is mapped in both {seen_users[user_id]} and {name}")
            seen_users[user_id] = name
        for path in (token_path, map_path, Path(project["webhook_posts"])):
            existing = path if path.exists() else path.parent
            if not os.access(existing, os.R_OK | os.W_OK):
                failures.append(f"{name}: ec2-user cannot read/write {path}")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nPASS: project files are separate, readable, writable, and unambiguous.")
    print("NOTE: incomplete coverage is acceptable only for inactive participants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
