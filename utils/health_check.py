"""Check listener, subscriptions, token files, maps, disk, memory, and delivery age."""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from config import callback_url, load_config
from utils.file_io import read_json
from utils.notify import notify
from utils.subscriptions import DATA_TYPES, EVENT_TYPES, SubscriptionClient, is_expired

LOG = logging.getLogger(__name__)


def run_checks(config: dict) -> list[str]:
    failures: list[str] = []
    try:
        response = requests.get(f"{config['server_address'].rstrip('/')}/healthz", timeout=20)
        if response.status_code != 200:
            failures.append(f"public health endpoint returned HTTP {response.status_code}")
    except requests.RequestException as error:
        failures.append(f"public health endpoint failed: {error.__class__.__name__}")

    try:
        subscriptions = SubscriptionClient(config).list()
        expected_keys = {
            (data_type, event_type)
            for data_type in DATA_TYPES
            for event_type in EVENT_TYPES
        }
        active_keys = {
            (sub.get("data_type"), sub.get("event_type"))
            for sub in subscriptions
            if not is_expired(sub) and sub.get("callback_url") == callback_url(config)
        }
        missing = expected_keys - active_keys
        if missing:
            failures.append(f"{len(missing)} required active subscriptions are missing or misrouted")
        obsolete_expired = [
            sub
            for sub in subscriptions
            if is_expired(sub)
            and (sub.get("data_type"), sub.get("event_type")) not in expected_keys
        ]
        if obsolete_expired:
            LOG.warning(
                "%s expired non-required subscriptions retained",
                len(obsolete_expired),
            )
    except (RuntimeError, requests.RequestException) as error:
        failures.append(f"subscription check failed: {error.__class__.__name__}")

    now = time.time()
    for name, project in config["projects"].items():
        token_path = Path(project["token_file"])
        if not token_path.exists():
            failures.append(f"{name}: token file missing")
        elif now - token_path.stat().st_mtime > 25 * 3600:
            failures.append(f"{name}: token file has not changed in 25 hours")
        mapping = read_json(project["participant_map"], None)
        if not isinstance(mapping, dict):
            failures.append(f"{name}: participant map missing or invalid")
        elif not mapping:
            LOG.warning("%s: participant map is empty (acceptable while inactive)", name)

    heartbeat = Path("/run/oura-listener/webhook.last")
    if not heartbeat.exists():
        failures.append("no webhook delivery has been observed since service start")
    elif now - heartbeat.stat().st_mtime > 24 * 3600:
        failures.append("no webhook delivery observed in 24 hours")

    usage = shutil.disk_usage("/")
    if usage.used / usage.total >= 0.85:
        failures.append(f"root disk is {usage.used / usage.total:.0%} full")
    try:
        memory = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, value = line.split(":", 1)
                memory[key] = int(value.strip().split()[0])
        if memory.get("MemAvailable", 0) < 64 * 1024:
            failures.append("less than 64 MiB memory is available")
    except (OSError, ValueError):
        pass
    return failures


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    failures = run_checks(config)
    if not failures:
        LOG.info("All Oura checks passed at %s", datetime.now(timezone.utc).isoformat())
        return 0
    message = "Oura listener health check failed:\n- " + "\n- ".join(failures)
    LOG.error(message)
    try:
        notify(message)
    except requests.RequestException:
        LOG.exception("Slack notification failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
