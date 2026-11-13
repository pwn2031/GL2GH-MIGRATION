"""Logging and run metadata helpers."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    return path


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def result_record(**kwargs):
    record = {"timestamp_utc": now_utc()}
    record.update(kwargs)
    return record


def log(message):
    print(f"[{now_utc()}] {message}")


def workspace_path(env_key, default_name):
    workspace = Path(os.environ.get("WORKSPACE_DIR", Path.home() / "gitlab-group-migration-automation"))
    return workspace / default_name