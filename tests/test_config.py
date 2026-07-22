import json

import pytest

from config import load_config


def test_config_rejects_embedded_secrets(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "client_secret": "must-not-be-here",
                "projects": {"test": {}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OURA_CLIENT_ID", "client-id")
    monkeypatch.setenv("OURA_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OURA_VERIFICATION_TOKEN", "verification-token")

    with pytest.raises(ValueError, match="Remove secret keys"):
        load_config(str(path))
