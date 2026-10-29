import unittest
from scripts.fetch_feeds import parse_date


class FeedDateTests(unittest.TestCase):
    def test_korean_feed_without_offset(self):
        self.assertEqual(parse_date("2026-10-29 09:42:26", "Asia/Seoul"), "2026-10-29T00:42:26Z")

    def test_explicit_offset_is_preserved(self):
        self.assertEqual(parse_date("2026-10-29T09:42:26+09:00", "UTC"), "2026-10-29T00:42:26Z")

    def test_default_remains_utc(self):
        self.assertEqual(parse_date("2026-10-29 09:42:26"), "2026-10-29T09:42:26Z")
