import json
import os
import sqlite3
import tempfile
import unittest

from migration_support import create_snapshot


class SnapshotTests(unittest.TestCase):
    def test_create_snapshot_copies_database_and_sidecar_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            snapshot_dir = os.path.join(tmpdir, "snapshot")
            os.makedirs(source_dir, exist_ok=True)

            db_path = os.path.join(source_dir, "agent.db")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, title TEXT)")
            cur.execute("INSERT INTO items (title) VALUES ('hello')")
            conn.commit()
            conn.close()

            control_path = os.path.join(source_dir, "control.json")
            with open(control_path, "w", encoding="utf-8") as f:
                json.dump({"paused": False}, f)

            bulk_state_file = os.path.join(source_dir, "bulk_copy_state.json")
            with open(bulk_state_file, "w", encoding="utf-8") as f:
                json.dump({"1": 99}, f)

            session_prefix = os.path.join(source_dir, "telethon_agent_a")
            with open(session_prefix + ".session", "w", encoding="utf-8") as f:
                f.write("session-data")

            manifest = create_snapshot(
                snapshot_dir=snapshot_dir,
                db_path=db_path,
                control_path=control_path,
                bulk_state_file=bulk_state_file,
                telethon_session_name=session_prefix,
            )

            self.assertTrue(os.path.exists(os.path.join(snapshot_dir, "agent.db")))
            self.assertTrue(os.path.exists(os.path.join(snapshot_dir, "control.json")))
            self.assertTrue(os.path.exists(os.path.join(snapshot_dir, "bulk_copy_state.json")))
            self.assertTrue(os.path.exists(os.path.join(snapshot_dir, "telethon_agent_a.session")))
            self.assertTrue(os.path.exists(os.path.join(snapshot_dir, "manifest.json")))
            self.assertEqual(manifest["files"]["db"], "agent.db")

            copied = sqlite3.connect(os.path.join(snapshot_dir, "agent.db"))
            row = copied.execute("SELECT title FROM items").fetchone()
            copied.close()
            self.assertEqual(row[0], "hello")


if __name__ == "__main__":
    unittest.main()
