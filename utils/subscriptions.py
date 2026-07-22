"""List, create, renew, repair, and delete app-level Oura subscriptions."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from config import callback_url, load_config

LOG = logging.getLogger(__name__)
API = "https://api.ouraring.com/v2/webhook/subscription"
DATA_TYPES = (
    "tag",
    "enhanced_tag",
    "workout",
    "session",
    "sleep",
    "daily_sleep",
    "daily_readiness",
    "daily_activity",
    "daily_spo2",
    "sleep_time",
    "rest_mode_period",
    "daily_stress",
    "daily_cardiovascular_age",
    "daily_resilience",
    "vo2_max",
)
EVENT_TYPES = ("create", "update")


class SubscriptionClient:
    def __init__(self, config: dict):
        self.config = config
        self.headers = {
            "x-client-id": config["client_id"],
            "x-client-secret": config["client_secret"],
            "Content-Type": "application/json",
        }

    def request(self, method: str, url: str, **kwargs):
        response = requests.request(method, url, headers=self.headers, timeout=30, **kwargs)
        if not response.ok:
            raise RuntimeError(f"Oura subscription API returned HTTP {response.status_code}: {response.text}")
        return response

    def list(self) -> list[dict]:
        data = self.request("GET", API).json()
        return data if isinstance(data, list) else data.get("data", [])

    def create(self, data_type: str, event_type: str) -> dict:
        payload = {
            "callback_url": callback_url(self.config),
            "verification_token": self.config["verification_token"],
            "data_type": data_type,
            "event_type": event_type,
        }
        return self.request("POST", API, json=payload).json()

    def update(self, subscription: dict) -> dict:
        payload = {
            "callback_url": callback_url(self.config),
            "verification_token": self.config["verification_token"],
            "data_type": subscription["data_type"],
            "event_type": subscription["event_type"],
        }
        return self.request("PUT", f"{API}/{subscription['id']}", json=payload).json()

    def renew(self, subscription_id: str) -> dict:
        return self.request("PUT", f"{API}/renew/{subscription_id}").json()

    def delete(self, subscription_id: str) -> None:
        self.request("DELETE", f"{API}/{subscription_id}")


def _expiry(subscription: dict) -> Optional[datetime]:
    value = subscription.get("expiration_time")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_expired(subscription: dict, now: Optional[datetime] = None) -> bool:
    expiry = _expiry(subscription)
    return expiry is None or expiry <= (now or datetime.now(timezone.utc))


def print_subscriptions(subscriptions: list[dict]) -> None:
    now = datetime.now(timezone.utc)
    if not subscriptions:
        print("No subscriptions found.")
        return
    for sub in sorted(subscriptions, key=lambda item: (item.get("data_type", ""), item.get("event_type", ""))):
        state = "EXPIRED" if is_expired(sub, now) else "ACTIVE"
        callback = sub.get("callback_url", "?")
        print(
            f"{state:7} {sub.get('data_type', '?'):28} {sub.get('event_type', '?'):6} "
            f"expires={sub.get('expiration_time', '?')} id={sub.get('id', '?')} callback={callback}"
        )


def ensure_subscriptions(client: SubscriptionClient, force_update: bool = False, renew_days: int = 21) -> int:
    subscriptions = client.list()
    expected = {(data_type, event_type) for data_type in DATA_TYPES for event_type in EVENT_TYPES}
    grouped: dict[tuple[str, str], list[dict]] = {}
    for sub in subscriptions:
        grouped.setdefault((sub.get("data_type"), sub.get("event_type")), []).append(sub)

    failures = 0
    now = datetime.now(timezone.utc)
    renew_before = now + timedelta(days=renew_days)
    for key in sorted(expected):
        candidates = grouped.get(key, [])
        usable = [sub for sub in candidates if not is_expired(sub, now)]
        subscription = usable[0] if usable else (candidates[0] if candidates else None)
        data_type, event_type = key

        try:
            if subscription is None:
                client.create(data_type, event_type)
                LOG.info("Created subscription %s/%s", data_type, event_type)
                continue
            if is_expired(subscription, now):
                needs_update = force_update or subscription.get("callback_url") != callback_url(
                    client.config
                )
                updated = False
                if needs_update:
                    try:
                        client.update(subscription)
                        updated = True
                        LOG.info("Updated expired subscription %s/%s", data_type, event_type)
                    except RuntimeError:
                        LOG.warning("Direct update failed; attempting renewal %s/%s", data_type, event_type)
                try:
                    client.renew(subscription["id"])
                    if needs_update and not updated:
                        client.update(subscription)
                    LOG.info("Renewed expired subscription %s/%s", data_type, event_type)
                except RuntimeError:
                    try:
                        client.create(data_type, event_type)
                    except RuntimeError as error:
                        if "HTTP 422" not in str(error):
                            raise
                        client.delete(subscription["id"])
                        client.create(data_type, event_type)
                    LOG.info("Replaced expired subscription %s/%s", data_type, event_type)
                continue
            if force_update or subscription.get("callback_url") != callback_url(client.config):
                client.update(subscription)
                LOG.info("Updated subscription %s/%s", data_type, event_type)
                if (_expiry(subscription) or now) <= renew_before:
                    client.renew(subscription["id"])
                    LOG.info("Renewed subscription %s/%s", data_type, event_type)
            elif (_expiry(subscription) or now) <= renew_before:
                client.renew(subscription["id"])
                LOG.info("Renewed subscription %s/%s", data_type, event_type)
        except (KeyError, RuntimeError) as error:
            failures += 1
            LOG.error("Failed subscription %s/%s: %s", data_type, event_type, error)

    for key, candidates in grouped.items():
        if key not in expected:
            LOG.warning("Unexpected subscription retained: %s/%s", *key)
        if len(candidates) > 1:
            LOG.warning("Duplicate subscriptions retained: %s/%s count=%s", *key, len(candidates))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    ensure = subparsers.add_parser("ensure")
    ensure.add_argument("--force-update", action="store_true")
    delete = subparsers.add_parser("delete")
    delete.add_argument("--id")
    delete.add_argument("--expired", action="store_true")
    delete.add_argument("--all", action="store_true")
    delete.add_argument("--yes", action="store_true", help="Required confirmation")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = SubscriptionClient(load_config())
    if args.command == "list":
        print_subscriptions(client.list())
        return 0
    if args.command == "ensure":
        return 1 if ensure_subscriptions(client, args.force_update) else 0
    if not args.yes:
        parser.error("delete requires --yes")
    if not (args.id or args.expired or args.all):
        parser.error("delete requires --id, --expired, or --all")
    targets = [
        sub
        for sub in client.list()
        if args.all or sub.get("id") == args.id or (args.expired and is_expired(sub))
    ]
    for target in targets:
        client.delete(target["id"])
        LOG.info("Deleted subscription id=%s", target["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
