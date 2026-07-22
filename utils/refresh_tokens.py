"""Refresh every project's Oura tokens safely, one time each."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

import requests

from config import load_config
from utils.file_io import atomic_write_json, file_lock, read_json

LOG = logging.getLogger(__name__)
TOKEN_URL = "https://api.ouraring.com/oauth/token"
PERSONAL_URL = "https://api.ouraring.com/v2/usercollection/personal_info"


def _reference(participant_id: str) -> str:
    return hashlib.sha256(participant_id.encode()).hexdigest()[:10]


def _repair_map(project: dict, participant_id: str, access_token: str) -> None:
    try:
        response = requests.get(
            PERSONAL_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        body = response.json() if response.status_code == 200 else {}
    except (requests.RequestException, ValueError):
        return
    if not body.get("id"):
        return
    map_path = project["participant_map"]
    with file_lock(map_path):
        mapping = read_json(map_path, {})
        mapping[body["id"]] = participant_id
        atomic_write_json(map_path, mapping)


def refresh_project(name: str, project: dict, config: dict) -> int:
    token_path = project["token_file"]
    failures = 0
    with file_lock(token_path):
        all_tokens = read_json(token_path, {})
        if not isinstance(all_tokens, dict):
            LOG.error("Invalid token file project=%s", name)
            return 1
        for participant_id in list(all_tokens):
            tokens = all_tokens[participant_id]
            reference = _reference(str(participant_id))
            if tokens.get("refresh_disabled"):
                LOG.info("Skipped disabled token project=%s participant_ref=%s", name, reference)
                continue
            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                LOG.error("Missing refresh token project=%s participant_ref=%s", name, reference)
                failures += 1
                continue
            # Do not retry: Oura refresh tokens are single-use.
            try:
                response = requests.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                    },
                    timeout=30,
                )
            except requests.RequestException as error:
                LOG.error(
                    "Refresh request failed project=%s participant_ref=%s error=%s",
                    name,
                    reference,
                    error.__class__.__name__,
                )
                failures += 1
                continue
            if response.status_code != 200:
                LOG.error(
                    "Refresh failed project=%s participant_ref=%s status=%s",
                    name,
                    reference,
                    response.status_code,
                )
                failures += 1
                continue
            try:
                refreshed = response.json()
            except ValueError:
                LOG.error("Invalid refresh response project=%s participant_ref=%s", name, reference)
                failures += 1
                continue
            if not refreshed.get("access_token"):
                LOG.error("Refresh response omitted access token project=%s participant_ref=%s", name, reference)
                failures += 1
                continue
            if not refreshed.get("refresh_token"):
                LOG.error("Refresh response omitted next refresh token project=%s participant_ref=%s", name, reference)
                failures += 1
            tokens.update(refreshed)
            tokens["last_refreshed"] = datetime.now(timezone.utc).isoformat()
            if refreshed.get("expires_in"):
                tokens["expires_at"] = (
                    datetime.now(timezone.utc) + timedelta(seconds=int(refreshed["expires_in"]))
                ).isoformat()
            all_tokens[participant_id] = tokens
            atomic_write_json(token_path, all_tokens)
            _repair_map(project, participant_id, tokens["access_token"])
            LOG.info("Refreshed project=%s participant_ref=%s", name, reference)
    return failures


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    failures = sum(
        refresh_project(name, project, config) for name, project in config["projects"].items()
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
