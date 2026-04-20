import os
import sqlite3
import tempfile
import unittest

from runtime_support import (
    ensure_items_schema,
    get_db_path,
    get_control_path,
    get_telethon_session_name,
    parse_post_limit,
)


class SchemaTests(unittest.TestCase):
    def test_ensure_items_schema_creates_processed_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "agent.db")
            cols = ensure_items_schema(db_path)
            self.assertIn("processed", cols)
            self.assertIn("processed_at_utc", cols)
            self.assertIn("source_message_id", cols)
            self.assertIn("website_published", cols)
            self.assertIn("telegram_published", cols)
            self.assertIn("source_deleted", cols)

    def test_ensure_items_schema_migrates_existing_items_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "agent.db")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_chat_id TEXT NOT NULL,
                    source_message_id INTEGER NOT NULL,
                    source_date_utc TEXT NOT NULL,
                    title TEXT,
                    title_norm TEXT,
                    url TEXT,
                    url_norm TEXT,
                    note TEXT,
                    fp_title TEXT,
                    fp_url TEXT,
                    raw_json TEXT,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()

            cols = ensure_items_schema(db_path)

            self.assertIn("processed", cols)
            self.assertIn("processed_at_utc", cols)

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(items)")
            live_cols = {row[1] for row in cur.fetchall()}
            conn.close()

            self.assertIn("processed", live_cols)
            self.assertIn("processed_at_utc", live_cols)
            self.assertIn("website_published", live_cols)
            self.assertIn("telegram_published", live_cols)
            self.assertIn("source_deleted", live_cols)


class RuntimeConfigTests(unittest.TestCase):
    def test_runtime_paths_follow_environment(self):
        env = {
            "DB_PATH": "/tmp/custom.db",
            "CONTROL_PATH": "/tmp/control-a.json",
            "TELETHON_SESSION_NAME": "telethon_agent_a",
        }
        self.assertEqual(get_db_path(env=env), "/tmp/custom.db")
        self.assertEqual(get_control_path(env=env), "/tmp/control-a.json")
        self.assertEqual(get_telethon_session_name(env=env), "telethon_agent_a")

    def test_parse_post_limit_prefers_cli_over_env(self):
        env = {"POST_LIMIT": "9"}
        self.assertEqual(parse_post_limit(["--limit", "3"], env=env), 3)
        self.assertEqual(parse_post_limit([], env=env), 9)
        self.assertEqual(parse_post_limit([], env={}), 5)


if __name__ == "__main__":
    unittest.main()
