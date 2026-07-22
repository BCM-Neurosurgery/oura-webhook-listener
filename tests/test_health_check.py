import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from utils import health_check
from utils.subscriptions import DATA_TYPES, EVENT_TYPES


def test_expired_non_required_subscriptions_do_not_fail_health(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(days=100)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    subscriptions = [
        {
            "data_type": data_type,
            "event_type": event_type,
            "callback_url": "https://ouralisten.bcmelias.com/oura-webhook",
            "expiration_time": future,
        }
        for data_type in DATA_TYPES
        for event_type in EVENT_TYPES
    ]
    subscriptions.extend(
        {
            "data_type": "ring_configuration",
            "event_type": event_type,
            "callback_url": "https://ouralisten.bcmelias.com/oura-webhook",
            "expiration_time": past,
        }
        for event_type in EVENT_TYPES
    )

    heartbeat = SimpleNamespace(
        exists=lambda: True,
        stat=lambda: SimpleNamespace(st_mtime=time.time()),
    )
    monkeypatch.setattr(
        health_check.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200),
    )
    monkeypatch.setattr(
        health_check.SubscriptionClient,
        "list",
        lambda self: subscriptions,
    )
    monkeypatch.setattr(health_check, "Path", lambda path: heartbeat)
    monkeypatch.setattr(
        health_check.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(used=10, total=100),
    )

    failures = health_check.run_checks(
        {
            "server_address": "https://ouralisten.bcmelias.com",
            "webhook_path": "/oura-webhook",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "projects": {},
        }
    )

    assert failures == []
