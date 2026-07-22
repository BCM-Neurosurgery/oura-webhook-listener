from utils import refresh_tokens
from utils.file_io import atomic_write_json, read_json


class Response:
    status_code = 200

    @staticmethod
    def json():
        return {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        }


def test_disabled_token_is_preserved_and_skipped(tmp_path, monkeypatch):
    token_file = tmp_path / "tokens.json"
    map_file = tmp_path / "map.json"
    atomic_write_json(
        token_file,
        {
            "inactive": {
                "refresh_token": "must-not-be-used",
                "refresh_disabled": True,
                "refresh_disabled_reason": "inactive",
            },
            "active": {"refresh_token": "valid-refresh-token"},
        },
    )
    atomic_write_json(map_file, {})
    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr(refresh_tokens.requests, "post", post)
    monkeypatch.setattr(refresh_tokens, "_repair_map", lambda *args: None)

    failures = refresh_tokens.refresh_project(
        "test",
        {"token_file": str(token_file), "participant_map": str(map_file)},
        {"client_id": "client-id", "client_secret": "client-secret"},
    )
    tokens = read_json(token_file, {})

    assert failures == 0
    assert len(calls) == 1
    assert tokens["inactive"]["refresh_token"] == "must-not-be-used"
    assert tokens["inactive"]["refresh_disabled"] is True
    assert tokens["active"]["refresh_token"] == "new-refresh-token"
