import hashlib
import hmac
from pathlib import Path

from flask import Flask

from routes import webhook


def _app(tmp_path: Path, monkeypatch) -> tuple[Flask, dict]:
    participant_map = tmp_path / "participant_map.json"
    participant_map.write_text('{"oura-user": "participant-1"}\n', encoding="utf-8")
    config = {
        "client_secret": "test-client-secret",
        "verification_token": "test-verification-token",
        "unmatched_webhook_posts": str(tmp_path / "unmatched"),
        "projects": {
            "test": {
                "participant_map": str(participant_map),
                "webhook_posts": str(tmp_path / "posts"),
            }
        },
    }
    monkeypatch.setattr(webhook, "HEARTBEAT", tmp_path / "webhook.last")
    app = Flask(__name__)
    app.config["OURA"] = config
    webhook.register_webhook_routes(app)
    return app, config


def _signature(body: bytes, timestamp: str, secret: str) -> str:
    return hmac.new(
        secret.encode(), timestamp.encode() + body, hashlib.sha256
    ).hexdigest().upper()


def test_exact_transmitted_body_signature_is_accepted(tmp_path, monkeypatch):
    app, config = _app(tmp_path, monkeypatch)
    body = b'{"event_type": "update", "data_type": "daily_stress", "user_id": "oura-user"}'
    timestamp = "1234567890"

    response = app.test_client().post(
        "/oura-webhook",
        data=body,
        content_type="application/json",
        headers={
            "x-oura-timestamp": timestamp,
            "x-oura-signature": _signature(body, timestamp, config["client_secret"]),
        },
    )

    assert response.status_code == 200
    assert len(list((tmp_path / "posts").rglob("*.json"))) == 1
    assert (tmp_path / "webhook.last").exists()


def test_invalid_signature_is_rejected(tmp_path, monkeypatch):
    app, _ = _app(tmp_path, monkeypatch)

    response = app.test_client().post(
        "/oura-webhook",
        json={"data_type": "sleep", "user_id": "oura-user"},
        headers={"x-oura-timestamp": "123", "x-oura-signature": "invalid"},
    )

    assert response.status_code == 401
    assert not (tmp_path / "webhook.last").exists()


def test_unknown_user_event_is_preserved(tmp_path, monkeypatch):
    app, config = _app(tmp_path, monkeypatch)
    body = b'{"data_type":"sleep","user_id":"unknown-user"}'
    timestamp = "1234567890"

    response = app.test_client().post(
        "/oura-webhook",
        data=body,
        content_type="application/json",
        headers={
            "x-oura-timestamp": timestamp,
            "x-oura-signature": _signature(body, timestamp, config["client_secret"]),
        },
    )

    assert response.status_code == 202
    assert len(list((tmp_path / "unmatched").glob("*.json"))) == 1
