import unittest
from datetime import datetime, timezone
from scripts.fetch_feeds import article_topics, merge_articles


class FeedPolicyTests(unittest.TestCase):
    def test_english_security_title(self):
        self.assertEqual(article_topics("GitLab Security Incident: CVE-2026-97229", {}), ["보안"])

    def test_model_and_retrieval_title(self):
        self.assertEqual(article_topics("한국어 문서 RAG 평가", {}), ["AI"])

    def test_specific_title_overrides_source_default(self):
        self.assertEqual(article_topics("전기차 배터리", {"type": "news", "topics": ["AI"]}), ["자동차"])

    def test_categories_help_classify(self):
        self.assertEqual(article_topics("새로운 소식", {}, "클라우드"), ["소프트웨어"])

    def test_source_fallback(self):
        self.assertEqual(article_topics("새로운 소식", {"topics": ["AI"]}), ["AI"])

    def test_daily_cap_keeps_quieter_source(self):
        sources = [{"id": "busy", "type": "news"}, {"id": "quiet", "type": "news"}]
        stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        articles = [{"id": str(i), "title": f"AI update {i}", "url": f"https://example.com/{i}", "summary": "", "publishedAt": stamp, "sourceIds": ["busy" if i < 25 else "quiet"], "topics": []} for i in range(26)]
        result = merge_articles([], articles, sources)
        self.assertEqual(len(result), 21)
        self.assertTrue(any(a["sourceIds"] == ["quiet"] for a in result))
