import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import discover_sources
import manage_subscription
from manage_subscription import apply_request, request_from_event


class SharedSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.feed_url = "https://example.com/rss.xml"
        self.candidate = {
            "id": discover_sources.candidate_id(self.feed_url),
            "name": "예시 기술 블로그",
            "siteUrl": "https://example.com/",
            "feedUrl": self.feed_url,
            "section": "tech",
            "kind": "blog",
        }

    def issue(self, author="jwjp", title="[구독] 예시 기술 블로그", body=None):
        return {"action": "opened", "issue": {"user": {"login": author}, "title": title,
                "body": body if body is not None else f"candidate_id: {self.candidate['id']}"}}

    def test_only_owner_can_request_changes(self):
        self.assertEqual(request_from_event(self.issue(), "jwjp/technews"), ("subscribe", self.candidate["id"]))
        with self.assertRaises(ValueError):
            request_from_event(self.issue(author="another-user"), "jwjp/technews")
        with self.assertRaises(ValueError):
            request_from_event(self.issue(body=f"candidate_id: {self.candidate['id']}\nother: value"), "jwjp/technews")

    @patch("manage_subscription.fetch_bytes", return_value=b"<rss><channel><title>Example</title></channel></rss>")
    def test_subscribe_duplicate_and_unsubscribe(self, fetch):
        sources, result = apply_request("subscribe", self.candidate["id"], [], [self.candidate])
        self.assertEqual(result, "subscribed")
        self.assertEqual(sources[0]["id"], f"candidate-{self.candidate['id']}")
        self.assertEqual(sources[0]["url"], self.feed_url)
        self.assertNotIn("type", sources[0])
        self.assertEqual(fetch.call_count, 1)
        unchanged, result = apply_request("subscribe", self.candidate["id"], sources, [self.candidate])
        self.assertEqual((unchanged, result), (sources, "already-subscribed"))
        remaining, result = apply_request("unsubscribe", sources[0]["id"], sources, [self.candidate])
        self.assertEqual((remaining, result), ([], "unsubscribed"))

    def test_unknown_and_tampered_candidates_are_rejected(self):
        with self.assertRaises(ValueError):
            apply_request("subscribe", self.candidate["id"], [], [])
        tampered = {**self.candidate, "feedUrl": "https://other.example/rss.xml"}
        with self.assertRaises(ValueError):
            apply_request("subscribe", self.candidate["id"], [], [tampered])

    def test_catalog_keeps_older_recommendations(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            with patch.object(discover_sources, "CATALOG", catalog):
                discover_sources.update_catalog([self.candidate])
                discover_sources.update_catalog([])
            saved = json.loads(catalog.read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in saved["sources"]], [self.candidate["id"]])

    @patch("manage_subscription.fetch_bytes", return_value=b"<rss><channel><title>Example</title></channel></rss>")
    def test_issue_updates_shared_list_and_action_output(self, fetch):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            sources, catalog, event, output = [folder / name for name in ("sources.json", "catalog.json", "event.json", "output.txt")]
            sources.write_text("[]", encoding="utf-8")
            catalog.write_text(json.dumps({"sources": [self.candidate]}), encoding="utf-8")
            event.write_text(json.dumps(self.issue()), encoding="utf-8")
            environment = {"GITHUB_EVENT_PATH": str(event), "GITHUB_REPOSITORY": "jwjp/technews", "GITHUB_OUTPUT": str(output)}
            with patch.object(manage_subscription, "SOURCES", sources), patch.object(manage_subscription, "CATALOG", catalog), patch.dict("os.environ", environment):
                self.assertEqual(manage_subscription.main(), 0)
            self.assertEqual(len(json.loads(sources.read_text(encoding="utf-8"))), 1)
            self.assertIn("changed=true\nresult=subscribed\n", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
