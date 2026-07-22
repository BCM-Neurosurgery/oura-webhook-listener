"""Send an optional Slack alert without exposing secrets."""

from __future__ import annotations

import argparse
import os

import requests


def notify(message: str) -> bool:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        return False
    response = requests.post(url, json={"text": message}, timeout=15)
    response.raise_for_status()
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("message")
    args = parser.parse_args()
    try:
        notify(args.message)
    except requests.RequestException:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
