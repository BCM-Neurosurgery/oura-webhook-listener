"""Locked JSON reads/writes and loss-resistant webhook storage."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Union
from zoneinfo import ZoneInfo


@contextmanager
def file_lock(path: Union[str, Path]):
    lock_path = Path(f"{path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def read_json(path: Union[str, Path], default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_json(path: Union[str, Path], data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_payload(root: Union[str, Path], payload: dict) -> Path:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(body).hexdigest()[:12]
    now = datetime.now(ZoneInfo("America/Chicago"))
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    directory = Path(root)
    with file_lock(directory / ".webhook-write"):
        path = directory / f"{timestamp}.json"
        if path.exists():
            path = directory / f"{timestamp}--{now.strftime('%f')}-{digest}.json"
        atomic_write_json(path, payload)
    return path
