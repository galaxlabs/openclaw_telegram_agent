#!/usr/bin/env python3
import glob
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_if_exists(source_path: str, dest_dir: str) -> str | None:
    if not source_path or not os.path.exists(source_path):
        return None
    dest_path = os.path.join(dest_dir, os.path.basename(source_path))
    shutil.copy2(source_path, dest_path)
    return os.path.basename(dest_path)


def backup_sqlite_db(source_db: str, dest_db: str) -> None:
    src = sqlite3.connect(source_db)
    dest = sqlite3.connect(dest_db)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()


def copy_session_files(session_prefix: str, dest_dir: str) -> list[str]:
    copied = []
    for path in sorted(glob.glob(session_prefix + "*")):
        if os.path.isdir(path):
            continue
        dest_path = os.path.join(dest_dir, os.path.basename(path))
        shutil.copy2(path, dest_path)
        copied.append(os.path.basename(dest_path))
    return copied


def create_snapshot(
    *,
    snapshot_dir: str,
    db_path: str,
    control_path: str | None = None,
    bulk_state_file: str | None = None,
    telethon_session_name: str | None = None,
) -> dict:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    os.makedirs(snapshot_dir, exist_ok=True)

    db_dest = os.path.join(snapshot_dir, "agent.db")
    backup_sqlite_db(db_path, db_dest)

    manifest = {
        "created_at_utc": now_iso(),
        "source": {
            "db_path": db_path,
            "control_path": control_path,
            "bulk_state_file": bulk_state_file,
            "telethon_session_name": telethon_session_name,
        },
        "files": {
            "db": "agent.db",
            "control": _copy_if_exists(control_path, snapshot_dir) if control_path else None,
            "bulk_state": _copy_if_exists(bulk_state_file, snapshot_dir) if bulk_state_file else None,
            "telethon_sessions": copy_session_files(telethon_session_name, snapshot_dir)
            if telethon_session_name
            else [],
        },
    }

    manifest_path = os.path.join(snapshot_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest
