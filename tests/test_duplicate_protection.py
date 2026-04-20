import os
import sqlite3
import tempfile
import unittest

from runtime_support import (
    build_dedupe_signature,
    ensure_items_schema,
    find_existing_item_by_signature,
)


class DedupeSchemaTests(unittest.TestCase):
    def test_ensure_items_schema_creates_dedupe_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "agent.db")
            cols = ensure_items_schema(db_path)
            self.assertIn("dedupe_signature", cols)
            self.assertIn("duplicate_of_item_id", cols)


class DedupeSignatureTests(unittest.TestCase):
    def test_url_signature_ignores_fragment_tracking_and_whitespace(self):
        a = build_dedupe_signature(
            title="Awesome Repo",
            url="https://github.com/openai/openai-python/?utm_source=telegram#readme",
            note="  Useful SDK link   ",
        )
        b = build_dedupe_signature(
            title="Awesome Repo",
            url="https://github.com/openai/openai-python",
            note="Useful SDK link",
        )
        self.assertEqual(a, b)

    def test_text_signature_uses_clean_title_and_note_when_url_missing(self):
        a = build_dedupe_signature(
            title="  Breaking: New AI tool  ",
            url="",
            note="  Same message body here ",
        )
        b = build_dedupe_signature(
            title="Breaking: New AI tool",
            url=None,
            note="Same message body here",
        )
        self.assertEqual(a, b)


class DedupeLookupTests(unittest.TestCase):
    def test_find_existing_item_by_signature_returns_prior_published_item(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "agent.db")
            ensure_items_schema(db_path)
            signature = build_dedupe_signature(
                title="Great GitHub repo",
                url="https://github.com/openai/openai-python",
                note="Useful SDK link",
            )

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO items (
                    source_chat_id, source_message_id, source_date_utc,
                    title, title_norm, url, url_norm, note,
                    fp_title, fp_url, raw_json, created_at_utc,
                    processed, website_published, telegram_published, dedupe_signature
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "-1001",
                    10,
                    "2026-04-18T00:00:00+00:00",
                    "Great GitHub repo",
                    "great github repo",
                    "https://github.com/openai/openai-python",
                    "https://github.com/openai/openai-python",
                    "Useful SDK link",
                    "fp1",
                    "fp2",
                    "{}",
                    "2026-04-18T00:00:00+00:00",
                    1,
                    1,
                    1,
                    signature,
                ),
            )
            cur.execute(
                """
                INSERT INTO items (
                    source_chat_id, source_message_id, source_date_utc,
                    title, title_norm, url, url_norm, note,
                    fp_title, fp_url, raw_json, created_at_utc,
                    processed, website_published, telegram_published, dedupe_signature
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "-1001",
                    11,
                    "2026-04-18T00:01:00+00:00",
                    "Great GitHub repo",
                    "great github repo",
                    "https://github.com/openai/openai-python",
                    "https://github.com/openai/openai-python",
                    "Useful SDK link",
                    "fp1",
                    "fp2",
                    "{}",
                    "2026-04-18T00:01:00+00:00",
                    0,
                    0,
                    0,
                    signature,
                ),
            )
            conn.commit()
            conn.close()

            duplicate_of = find_existing_item_by_signature(
                db_path=db_path,
                signature=signature,
                exclude_item_id=2,
                require_published=True,
            )

            self.assertEqual(duplicate_of, 1)


if __name__ == "__main__":
    unittest.main()
