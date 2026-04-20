#!/usr/bin/env python3
import argparse
import os

from dotenv import load_dotenv

from migration_support import create_snapshot
from runtime_support import (
    get_bulk_state_file,
    get_control_path,
    get_db_path,
    get_telethon_session_name,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a safe local snapshot for remote migration.")
    parser.add_argument("--output-dir", required=True, help="Directory where the snapshot files will be written.")
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--control-path", default=None)
    parser.add_argument("--bulk-state-file", default=None)
    parser.add_argument("--telethon-session-name", default=None)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    manifest = create_snapshot(
        snapshot_dir=args.output_dir,
        db_path=args.db_path or get_db_path(os.path.join(os.getcwd(), "agent.db")),
        control_path=args.control_path or get_control_path(os.path.join(os.getcwd(), "control.json")),
        bulk_state_file=args.bulk_state_file or get_bulk_state_file(os.path.join(os.getcwd(), "bulk_copy_state.json")),
        telethon_session_name=args.telethon_session_name or get_telethon_session_name(os.path.join(os.getcwd(), "telethon_session")),
    )

    print(f"Snapshot created: {args.output_dir}")
    print(f"Manifest: {os.path.join(args.output_dir, 'manifest.json')}")
    print(f"Copied session files: {len(manifest['files']['telethon_sessions'])}")


if __name__ == "__main__":
    main()
