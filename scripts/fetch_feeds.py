#!/usr/bin/env python3
"""Fetch RSS/Atom into a small, safe JSON index for the static reader."""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources.json"
OUTPUT = ROOT / "site" / "data" / "articles.json"
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
TRACKING_KEYS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "source"}
AGGREGATOR_HOSTS = {"velopers.kr", "www.velopers.kr", "news.hada.io", "indieblog.net", "www.indieblog.net"}
MAX_FEED_BYTES = 5_000_000
MAX_AGE_DAYS = 180
SECTION_LIMITS = {"reading": 1000, "news": 1800, "economy-blog": 1000, "economy": 1800}
NEWS_TOPICS = ("기술", "개발", "소프트웨어", "보안", "AI", "자동차")
ECONOMY_TOPICS = ("주식", "금융", "부동산", "경제", "정책")
TITLE_TOPICS = {
    "개발": r"개발자|개발도구|개발환경|프로그래밍|코딩|오픈소스|깃허브|GitHub|DevOps|API\b|SDK\b",
    "소프트웨어": r"소프트웨어|\bSW\b|\bSaaS\b|클라우드|데이터베이스|운영체제|\bOS\b|애플리케이션|\b앱\b",
    "보안": r"보안|해킹|해커|랜섬웨어|악성코드|사이버공격|취약점|정보보호|개인정보|피싱",
    "AI": r"(?<![A-Za-z])AI(?![A-Za-z])|인공지능|생성형|LLM|챗봇|챗GPT|ChatGPT|머신러닝|딥러닝",
    "자동차": r"자동차|전기차|자율주행|모빌리티|완성차|현대차|기아차|테슬라|차량|배터리|충전소|로보택시|커넥티드카",
    "기술": r"반도체|디스플레이|스마트폰|컴퓨팅|통신망|네트워크|데이터센터|서버|로봇|양자컴퓨팅|기술개발",
}
ECONOMY_TITLE_TOPICS = {
    "주식": r"주식|증시|주가|코스피|코스닥|증권|상장|배당|ETF|IPO|공모주",
    "금융": r"금융|은행|대출|금리|채권|환율|보험|가계부채",
    "부동산": r"부동산|아파트|주택|집값|전세|월세|청약|분양|재건축|재개발|임대차|토지",
    "정책": r"정부|정책|대책|규제|세제|세금|예산|법안|국회|지원책|보도자료",
}


class PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg"}:
            self.hidden += 1
        elif tag in {"p", "br", "li", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self.hidden:
            self.hidden -= 1
        elif tag in {"p", "li", "div"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def clean_text(value: str | None, limit: int) -> str:
    parser = PlainText()
    parser.feed(value or "")
    value = html.unescape(" ".join(parser.parts))
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit].rstrip()


def child_text(element: ET.Element, *names: str) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def parse_date(raw: str, timezone_name: str = "UTC") -> str | None:
    if not raw:
        return None
    if re.fullmatch(r"\d{14}", raw):
        parsed = datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone(timedelta(hours=9)))
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None
    if parsed.tzinfo is None:
        feed_timezone = timezone(timedelta(hours=9)) if timezone_name == "Asia/Seoul" else timezone.utc
        parsed = parsed.replace(tzinfo=feed_timezone)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_url(raw: str) -> str | None:
    try:
        parsed = urllib.parse.urlsplit(raw.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname.lower()
        port = f":{parsed.port}" if parsed.port and parsed.port not in {80, 443} else ""
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query = [(key, value) for key, value in query if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS]
        path = parsed.path.rstrip("/") or "/"
        return urllib.parse.urlunsplit((parsed.scheme.lower(), host + port, path, urllib.parse.urlencode(query), ""))
    except ValueError:
        return None


def fetch_xml(url: str) -> ET.Element:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TechNewsPersonalReader/1.0 (RSS reader; https://github.com/jwjp/technews)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"},
    )
    error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                data = response.read(MAX_FEED_BYTES + 1)
            if len(data) > MAX_FEED_BYTES:
                raise ValueError("feed exceeds 5 MB")
            return ET.fromstring(data)
        except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as exc:
            error = exc
            if attempt == 0:
                time.sleep(1)
    raise RuntimeError(str(error))


def ordered_topics(topics: set[str]) -> list[str]:
    return [topic for topic in NEWS_TOPICS + ECONOMY_TOPICS if topic in topics]


def classify_news(title: str) -> list[str]:
    topics = {topic for topic, pattern in TITLE_TOPICS.items() if re.search(pattern, title, re.IGNORECASE)}
    return ordered_topics(topics)


def classify_economy(title: str) -> list[str]:
    topics = {topic for topic, pattern in ECONOMY_TITLE_TOPICS.items() if re.search(pattern, title, re.IGNORECASE)}
    return ordered_topics(topics)


def entries_from(root: ET.Element, source: dict) -> list[dict]:
    entries = root.findall(".//item") if root.tag != f"{ATOM}feed" else root.findall(f"{ATOM}entry")
    result = []
    for entry in entries[:150]:
        title = clean_text(child_text(entry, "title", f"{ATOM}title"), 220)
        if root.tag == f"{ATOM}feed":
            links = entry.findall(f"{ATOM}link")
            link = next((item.get("href", "") for item in links if item.get("rel", "alternate") == "alternate"), "")
            if not link and links:
                link = links[0].get("href", "")
        else:
            link = child_text(entry, "link")
        link = canonical_url(link)
        if not title or not link:
            continue
        published = parse_date(child_text(entry, "pubDate", f"{ATOM}published", f"{ATOM}updated", f"{DC}date"), source.get("timezone", "UTC"))
        if not published:
            continue
        topics = set(source.get("topics", []))
        if source.get("type") == "news":
            topics.update(classify_news(title))
        elif source.get("type") in {"economy", "economy-blog"}:
            topics.update(classify_economy(title))
        if source.get("classify") and not topics:
            continue
        description = child_text(entry, "description", f"{ATOM}summary", f"{ATOM}content")
        summary = "" if source.get("type") in {"news", "economy"} else clean_text(description, 280)
        if summary.casefold() == title.casefold():
            summary = ""
        result.append({
            "id": hashlib.sha256(link.encode("utf-8")).hexdigest()[:20],
            "title": title,
            "url": link,
            "summary": summary,
            "publishedAt": published,
            "sourceIds": [source["id"]],
            "topics": ordered_topics(topics),
        })
    return result


def title_key(article: dict) -> str:
    return re.sub(r"[^\w가-힣]", "", article["title"].casefold())


def link_quality(url: str) -> int:
    host = urllib.parse.urlsplit(url).hostname or ""
    return 0 if host in AGGREGATOR_HOSTS else 1


def merge_articles(old: list[dict], incoming: list[dict], sources: list[dict]) -> list[dict]:
    source_order = [source["id"] for source in sources]
    source_topics = {source["id"]: source.get("topics", []) for source in sources}
    news_sources = {source["id"] for source in sources if source.get("type") == "news"}
    economy_sources = {source["id"] for source in sources if source.get("type") == "economy"}
    economy_blogs = {source["id"] for source in sources if source.get("type") == "economy-blog"}
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    valid = []
    for article in old + incoming:
        try:
            known_sources = [source_id for source_id in article["sourceIds"] if source_id in source_order]
            if known_sources and cutoff <= datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00")) <= now + timedelta(minutes=15):
                topics: set[str] = set()
                for source_id in known_sources:
                    topics.update(source_topics[source_id])
                if any(source_id in news_sources for source_id in known_sources):
                    topics.update(classify_news(article["title"]))
                if any(source_id in economy_sources | economy_blogs for source_id in known_sources):
                    topics.update(classify_economy(article["title"]))
                if any(source_id in news_sources | economy_sources for source_id in known_sources) and not topics:
                    continue
                valid.append({**article, "sourceIds": known_sources, "topics": ordered_topics(topics)})
        except (KeyError, ValueError):
            continue
    valid.sort(key=lambda item: item["publishedAt"], reverse=True)
    merged: list[dict] = []
    by_url: dict[str, dict] = {}
    by_title: dict[str, list[dict]] = {}
    for article in valid:
        key = title_key(article)
        match = by_url.get(article["url"])
        if not match and len(key) >= 8:
            for candidate in by_title.get(key, []):
                left = datetime.fromisoformat(candidate["publishedAt"].replace("Z", "+00:00"))
                right = datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00"))
                if abs(left - right) <= timedelta(days=2):
                    match = candidate
                    break
        if match:
            match["sourceIds"] = sorted(set(match["sourceIds"] + article["sourceIds"]), key=source_order.index)
            match["topics"] = ordered_topics(set(match["topics"] + article["topics"]))
            if link_quality(article["url"]) > link_quality(match["url"]):
                match["url"] = article["url"]
            if not match.get("summary") and article.get("summary"):
                match["summary"] = article["summary"]
            by_url[article["url"]] = match
        else:
            copied = {key: article[key] for key in ("id", "title", "url", "summary", "publishedAt", "sourceIds", "topics")}
            copied["sourceIds"] = [source_id for source_id in source_order if source_id in copied["sourceIds"]]
            merged.append(copied)
            by_url[copied["url"]] = copied
            by_title.setdefault(key, []).append(copied)
    section_counts = {section: 0 for section in SECTION_LIMITS}
    kept = []
    for article in merged:
        ids = set(article["sourceIds"])
        section = "economy-blog" if ids & economy_blogs else "economy" if ids & economy_sources else "news" if ids & news_sources else "reading"
        if section_counts[section] < SECTION_LIMITS[section]:
            kept.append(article)
            section_counts[section] += 1
    return kept


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-all", action="store_true", help="Fail if any feed fails")
    args = parser.parse_args()
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    old_doc = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"articles": []}
    incoming: list[dict] = []
    failures = []
    health = []
    for source in sources:
        try:
            entries = entries_from(fetch_xml(source["url"]), source)
            if not entries:
                raise ValueError("no usable entries")
            incoming.extend(entries)
            health.append({"id": source["id"], "ok": True, "count": len(entries)})
            print(f"{source['name']}: {len(entries)} entries")
        except Exception as exc:
            failures.append(source["id"])
            health.append({"id": source["id"], "ok": False, "count": 0})
            print(f"{source['name']}: {exc}", file=sys.stderr)
    if not incoming or (args.require_all and failures):
        return 1
    refreshed_urls = {article["url"] for article in incoming}
    previous = [article for article in old_doc.get("articles", []) if article["url"] not in refreshed_urls]
    merged = merge_articles(previous, incoming, sources)
    if incoming:
        document = {
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "sourceHealth": health,
            "sources": sources,
            "articles": merged,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {len(merged)} articles ({len(failures)} failed feeds)")
    else:
        print(f"No change ({len(merged)} articles, {len(failures)} failed feeds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
