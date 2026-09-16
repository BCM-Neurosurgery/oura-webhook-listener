"""Safe JSON storage for webhook payloads and enrollment metadata."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


@contextmanager
def file_lock(path: str | Path):
    """Hold an advisory lock for one JSON resource."""
    lock_path = Path(path).with_suffix(Path(path).suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_json(path: str | Path, default: Any) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_json(path: str | Path, data: Any) -> Path:
    """Replace a JSON file atomically after its full contents reach disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def _safe_component(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        return None
    return value


def _save_payload(directory: str | Path, payload: dict) -> Path:
    """Save an event without replacing a concurrent delivery."""
    directory = Path(directory)
    timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%dT%H-%M-%S-%f")
    path = directory / f"{timestamp}-{uuid.uuid4().hex}.json"
    with file_lock(directory / ".webhook-write"):
        return atomic_write_json(path, payload)


def save_webhook_data(data: dict, config: dict) -> bool:
    """Store a mapped event, or preserve an unmapped event for review.

    Returns ``True`` only when an explicit participant map determined the
    destination. The former "next unmapped participant" fallback is
    intentionally absent: it could assign one person's data to another.
    """
    unmatched_directory = Path(config["data_dir"]) / "unmatched_webhook_posts"
    user_id = data.get("user_id")
    data_type = data.get("data_type")
    allowed_types = set(config.get("data_types", []))

    if (
        not isinstance(user_id, str)
        or not isinstance(data_type, str)
        or not user_id
        or not data_type
        or data_type not in allowed_types
    ):
        _save_payload(unmatched_directory, data)
        return False

    map_path = Path(config["data_dir"]) / "participant_map.json"
    with file_lock(map_path):
        participant_id = read_json(map_path, {}).get(str(user_id))
    participant_id = _safe_component(participant_id)
    data_type = _safe_component(data_type)
    if participant_id is None or data_type is None:
        _save_payload(unmatched_directory, data)
        return False

    _save_payload(Path(config["webhook_posts"]) / participant_id / data_type, data)
    return True

def send_webhook_signal(timestamp, path):
    _save_payload(path, {"event": "new_webhook", "timestamp": timestamp})
