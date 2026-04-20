import unittest

from publish_support import (
    build_website_payload,
    get_publish_config,
    is_item_fully_processed,
)


class PublishConfigTests(unittest.TestCase):
    def test_website_only_mode_is_valid(self):
        cfg = get_publish_config(
            {
                "WEBSITE_PUBLISH_ENABLED": "1",
                "WEBSITE_PUBLISH_URL": "https://example.vercel.app/api/publish",
                "TELEGRAM_BOT_TOKEN": "token",
            }
        )

        self.assertTrue(cfg["website_enabled"])
        self.assertFalse(cfg["telegram_enabled"])
        self.assertTrue(cfg["delete_enabled"])

    def test_delete_requires_bot_token(self):
        cfg = get_publish_config(
            {
                "WEBSITE_PUBLISH_ENABLED": "1",
                "WEBSITE_PUBLISH_URL": "https://example.vercel.app/api/publish",
                "DELETE_SOURCE_AFTER_PUBLISH": "1",
            }
        )

        self.assertFalse(cfg["delete_enabled"])


class PublishPayloadTests(unittest.TestCase):
    def test_build_website_payload_contains_useful_fields(self):
        payload = build_website_payload(
            {
                "id": 17,
                "title": "Great GitHub repo https://github.com/openai/openai-python",
                "url": "https://github.com/openai/openai-python",
                "note": "Useful SDK link with examples",
                "source_chat_id": "-100123",
                "source_message_id": 88,
                "source_date_utc": "2026-04-17T20:00:00+00:00",
            },
            "Great GitHub repo\nType: GITHUB | Source: github.com\nhttps://github.com/openai/openai-python",
        )

        self.assertEqual(payload["item_id"], 17)
        self.assertEqual(payload["category"], "GITHUB")
        self.assertEqual(payload["source_domain"], "github.com")
        self.assertEqual(payload["source"]["chat_id"], "-100123")
        self.assertIn("formatted_text", payload)


class PublishCompletionTests(unittest.TestCase):
    def test_item_completion_requires_all_enabled_steps(self):
        item = {
            "website_published": 1,
            "telegram_published": 1,
            "source_deleted": 0,
        }

        self.assertFalse(
            is_item_fully_processed(
                item=item,
                website_enabled=True,
                telegram_enabled=True,
                delete_enabled=True,
            )
        )

        item["source_deleted"] = 1
        self.assertTrue(
            is_item_fully_processed(
                item=item,
                website_enabled=True,
                telegram_enabled=True,
                delete_enabled=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
