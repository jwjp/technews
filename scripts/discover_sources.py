#!/usr/bin/env python3
"""Publish a small, checked list of weekly RSS source recommendations."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from fetch_feeds import ROOT, SOURCES, OUTPUT as ARTICLES, clean_text, entries_from, classify_news, classify_economy, child_text, ATOM


SEEDS = ROOT / "discovery_seeds.json"
OUTPUT = ROOT / "site" / "data" / "candidates.json"
AWESOME_LIST = "https://raw.githubusercontent.com/awesome-devblog/awesome-devblog/main/db.yml"
ECONOMY_RANKING = "https://blai.co.kr/blog-stats/ranking"
MAX_CATALOG_BYTES = 1_000_000
MAX_FEED_BYTES = 2_000_000
MAX_CHECKS = {"tech": 200, "economy": 25}
MAX_RECOMMENDATIONS = {"tech": 6, "economy": 6}
RECENT_DAYS = 120
ARCHIVE_LIMIT = 300
TECH_WORDS = re.compile(
    r"개발|개발자|프로그래밍|코드|코딩|서버|클라우드|데이터|보안|인공지능|자율주행|반도체|기술|"
    r"\b(?:AI|LLM|API|SDK|SQL|AWS|GCP|Java|Kotlin|Swift|Python|React|Vue|Node|Docker|Kubernetes|"
    r"Spring|Linux|Git|TypeScript|JavaScript|Rust|Go|Flutter|Android|iOS|Frontend|Backend|DevOps)\b",
    re.IGNORECASE,
)
ECONOMY_WORDS = re.compile(
    r"경제|주식|증시|증권|투자|기업|금융|은행|금리|환율|물가|부동산|아파트|주택|전세|청약|분양|"
    r"재건축|재개발|정책|정부|세금|대출|채권|배당|코스피|코스닥|\b(?:ETF|IPO|KOSPI|S&P|NASDAQ)\b",
    re.IGNORECASE,
)


def safe_http_url(raw: str) -> str | None:
    try:
        parsed = urllib.parse.urlsplit(raw.strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return None
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if not address.is_global:
                return None
        return urllib.parse.urlunsplit(("https", parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
    except ValueError:
        return None


def fetch_bytes(url: str, limit: int) -> bytes:
    checked = safe_http_url(url)
    if not checked:
        raise ValueError("unsafe URL")
    request = urllib.request.Request(
        checked,
        headers={"User-Agent": "TechNewsPersonalReader/1.0 (+https://github.com/jwjp/technews)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html, */*"},
    )
    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            if not safe_http_url(newurl):
                raise urllib.error.HTTPError(newurl, code, "unsafe redirect", headers, fp)
            return super().redirect_request(request, fp, code, msg, headers, newurl)

    with urllib.request.build_opener(SafeRedirect).open(request, timeout=12) as response:
        if not safe_http_url(response.url):
            raise ValueError("unsafe redirect")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("response too large")
    return data


class FeedLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        values = dict(attrs)
        if "alternate" in (values.get("rel") or "").lower().split() and (values.get("type") or "").lower() in {"application/rss+xml", "application/atom+xml"}:
            if values.get("href"):
                self.links.append(values["href"])


def discover_feed(site_url: str) -> str | None:
    page = fetch_bytes(site_url, MAX_FEED_BYTES)
    try:
        root = ET.fromstring(page)
        if root.tag in {"rss", f"{ATOM}feed"}:
            return safe_http_url(site_url)
    except ET.ParseError:
        pass
    parser = FeedLinks()
    parser.feed(page.decode("utf-8", errors="replace"))
    for href in parser.links:
        candidate = safe_http_url(urllib.parse.urljoin(site_url, href))
        if candidate:
            return candidate
    return None


def candidate_id(feed_url: str) -> str:
    return hashlib.sha256(feed_url.encode("utf-8")).hexdigest()[:16]


def awesome_candidates() -> list[dict]:
    raw = fetch_bytes(AWESOME_LIST, MAX_CATALOG_BYTES).decode("utf-8", errors="replace")
    found = []
    # The public catalog is a YAML list of small mappings. Only read three plain
    # URL/name fields; ignore other YAML rather than treating it as executable data.
    for block in re.split(r"(?m)^- name:\s*", raw)[1:]:
        lines = block.splitlines()
        name = lines[0].strip().strip('"\'')
        rss = re.search(r"(?m)^\s+rss:\s*(\S+)", block)
        blog = re.search(r"(?m)^\s+blog:\s*(\S+)", block)
        if not rss:
            continue
        feed_url = safe_http_url(rss.group(1).strip('"\''))
        site_url = safe_http_url(blog.group(1).strip('"\'')) if blog else None
        if feed_url and name:
            found.append({"name": name[:90], "siteUrl": site_url or feed_url, "feedUrl": feed_url,
                          "section": "tech", "kind": "blog", "foundVia": "Awesome Devblog"})
    return found


def economy_ranking_candidates() -> list[dict]:
    raw = fetch_bytes(ECONOMY_RANKING, MAX_CATALOG_BYTES).decode("utf-8", errors="replace")
    anchors = list(re.finditer(r'<a\b[^>]*href="https://blog\.naver\.com/([A-Za-z0-9_-]+)"[^>]*>(.*?)</a>', raw, re.I | re.S))
    found = []
    for index, anchor in enumerate(anchors):
        following = raw[anchor.end():anchors[index + 1].start() if index + 1 < len(anchors) else anchor.end() + 1500]
        if "비즈니스·경제" not in following:
            continue
        blog_id = anchor.group(1)
        name = clean_text(anchor.group(2), 90)
        if name:
            found.append({"name": name, "siteUrl": f"https://blog.naver.com/{blog_id}",
                          "feedUrl": f"https://rss.blog.naver.com/{blog_id}.xml", "section": "economy",
                          "kind": "blog", "foundVia": "경제 블로그 공개 목록"})
    return found


def normalized_feed(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def inspect_candidate(candidate: dict, existing_article_urls: set[str], now: datetime) -> dict | None:
    feed_url = safe_http_url(candidate.get("feedUrl", "")) or discover_feed(candidate["siteUrl"])
    if not feed_url:
        return None
    root = ET.fromstring(fetch_bytes(feed_url, MAX_FEED_BYTES))
    if root.tag not in {"rss", f"{ATOM}feed"}:
        return None
    is_economy = candidate["section"] == "economy"
    source = {"id": "candidate", "type": "economy-blog" if is_economy and candidate["kind"] == "blog" else "economy" if is_economy else "news", "topics": candidate.get("topics", [])}
    entries = entries_from(root, source)
    cutoff = now - timedelta(days=RECENT_DAYS)
    recent = []
    for entry in entries:
        published = datetime.fromisoformat(entry["publishedAt"].replace("Z", "+00:00"))
        if cutoff <= published <= now + timedelta(days=1):
            recent.append(entry)
    if len(recent) < 2:
        return None
    recent.sort(key=lambda item: item["publishedAt"], reverse=True)
    sample = recent[:12]
    matcher = ECONOMY_WORDS if is_economy else TECH_WORDS
    relevant = sum(bool(matcher.search(entry["title"])) for entry in sample)
    if relevant < (2 if candidate["kind"] == "blog" else 1):
        return None
    overlap = sum(entry["url"] in existing_article_urls for entry in sample)
    channel = root.find("channel")
    feed_title = clean_text(child_text(channel if channel is not None else root, "title", f"{ATOM}title"), 90)
    channel_link = child_text(channel, "link") if channel is not None else ""
    site_url = safe_http_url(candidate.get("siteUrl", "")) or safe_http_url(channel_link) or feed_url
    topics = set(candidate.get("topics", []))
    classifier = classify_economy if is_economy else classify_news
    for entry in sample:
        topics.update(classifier(entry["title"]))
    score = relevant * 4 + min(len(recent), 10) + max(0, 30 - (now - datetime.fromisoformat(recent[0]["publishedAt"].replace("Z", "+00:00"))).days) // 5
    score += max(0, len(sample) - overlap)
    return {
        "id": candidate_id(feed_url),
        "name": (feed_title if candidate.get("foundVia") == "Awesome Devblog" else candidate.get("name")) or feed_title or urllib.parse.urlsplit(site_url).hostname,
        "siteUrl": site_url,
        "feedUrl": feed_url,
        "section": candidate["section"],
        "kind": candidate["kind"],
        "topics": sorted(topics),
        "latestAt": recent[0]["publishedAt"],
        "checkedAt": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "recentCount": len(recent),
        "overlapCount": overlap,
        "foundVia": candidate.get("foundVia", "RSS 자동 발견"),
        "samples": [{"title": entry["title"], "url": entry["url"], "publishedAt": entry["publishedAt"]} for entry in recent[:3]],
        "score": score,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing output")
    parser.add_argument("--force", action="store_true", help="Refresh even if this week was already published")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    week = now.astimezone(timezone(timedelta(hours=9))).strftime("%G-W%V")
    existing_sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    existing_feeds = {normalized_feed(source["url"]) for source in existing_sources}
    article_doc = json.loads(ARTICLES.read_text(encoding="utf-8")) if ARTICLES.exists() else {"articles": []}
    article_urls = {article["url"] for article in article_doc.get("articles", [])}
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    if previous.get("week") == week and previous.get("candidates") and not args.force:
        print(f"Week {week} already published; use --force to refresh")
        return 0
    archive = previous.get("archive", []) + previous.get("candidates", [])
    archive = list({item["id"]: item for item in archive if isinstance(item, dict) and "id" in item}.values())
    shown_ids = {item["id"] for item in archive}
    raw_candidates = json.loads(SEEDS.read_text(encoding="utf-8"))
    for label, loader in [("Awesome Devblog", awesome_candidates), ("경제 블로그 공개 목록", economy_ranking_candidates)]:
        try:
            found = loader()
            raw_candidates.extend(found)
            print(f"{label}: {len(found)} listed sources")
        except Exception as exc:
            print(f"{label}: {exc}", file=sys.stderr)
    unique: dict[str, dict] = {}
    for candidate in raw_candidates:
        feed_url = safe_http_url(candidate.get("feedUrl", ""))
        site_url = safe_http_url(candidate.get("siteUrl", ""))
        if not site_url or candidate.get("section") not in MAX_CHECKS or candidate.get("kind") not in {"blog", "news", "policy"}:
            continue
        if feed_url and normalized_feed(feed_url) in existing_feeds:
            continue
        unique.setdefault(normalized_feed(feed_url or site_url), candidate)
    checked: list[dict] = []
    for section, limit in MAX_CHECKS.items():
        candidates = [item for item in unique.values() if item["section"] == section]
        candidates.sort(key=lambda item: (candidate_id(item.get("feedUrl") or item["siteUrl"]) in shown_ids,
                                          hashlib.sha256(f"{week}:{item.get('feedUrl') or item['siteUrl']}".encode()).hexdigest()))
        checked.extend(candidates[:limit])
    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(inspect_candidate, item, article_urls, now): item for item in checked}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
                if result and normalized_feed(result["feedUrl"]) not in existing_feeds:
                    results.append(result)
            except Exception as exc:
                print(f"Skipped {item.get('name', item['siteUrl'])}: {exc}", file=sys.stderr)
    # Keep recently verified candidates available when a directory or feed has a
    # temporary outage. Older checks must be validated again before reuse.
    by_id = {item["id"]: item for item in results}
    for item in archive:
        try:
            checked_at = datetime.fromisoformat(item.get("checkedAt", previous.get("generatedAt", "")).replace("Z", "+00:00"))
            latest_at = datetime.fromisoformat(item["latestAt"].replace("Z", "+00:00"))
            if now - checked_at <= timedelta(days=14) and now - latest_at <= timedelta(days=RECENT_DAYS) and normalized_feed(item["feedUrl"]) not in existing_feeds:
                by_id.setdefault(item["id"], item)
        except (KeyError, ValueError):
            continue
    results = list(by_id.values())
    recommendations = []
    for section in MAX_RECOMMENDATIONS:
        subset = [item for item in results if item["section"] == section]
        subset.sort(key=lambda item: (item["id"] in shown_ids, -item["score"], item["name"]))
        recommendations.extend(subset[:MAX_RECOMMENDATIONS[section]])
    current_ids = {item["id"] for item in recommendations}
    archive = [item for item in archive if item["id"] not in current_ids and normalized_feed(item.get("feedUrl", "")) not in existing_feeds]
    archive = archive[-ARCHIVE_LIMIT:]
    document = {"generatedAt": now.isoformat(timespec="seconds").replace("+00:00", "Z"), "week": week,
                "candidates": recommendations, "archive": archive}
    print(f"Checked {len(checked)} feeds; recommended {len(recommendations)} sources (tech {sum(c['section'] == 'tech' for c in recommendations)}, economy {sum(c['section'] == 'economy' for c in recommendations)})")
    if not args.dry_run:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
