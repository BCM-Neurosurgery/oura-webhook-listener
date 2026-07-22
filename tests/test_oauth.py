from urllib.parse import parse_qs, urlparse

from flask import Flask

from routes.oauth import register_oauth_routes


def test_project_authorize_route_uses_project_callback():
    app = Flask(__name__)
    app.config["OURA"] = {
        "client_id": "client-id",
        "verification_token": "verification-token",
        "oauth_state_secret": "state-secret",
        "server_address": "https://ouralisten.bcmelias.com",
        "projects": {"trbd": {}},
    }
    register_oauth_routes(app)

    response = app.test_client().get(
        "/trbd/authorize?participant_id=MIGRATION_TEST"
    )
    parameters = parse_qs(urlparse(response.headers["Location"]).query)

    assert response.status_code == 302
    assert parameters["redirect_uri"] == [
        "https://ouralisten.bcmelias.com/trbd/callback"
    ]
    assert parameters["state"][0] != "MIGRATION_TEST"
