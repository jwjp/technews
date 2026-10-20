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
AGGREGATOR_HOSTS = {"velopers.kr", "www.velopers.kr", "news.hada.io"}
MAX_FEED_BYTES = 5_000_000
MAX_ARTICLES = 2000
MAX_AGE_DAYS = 180


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


def parse_date(raw: str) -> str | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
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


def entries_from(root: ET.Element, source: dict[str, str]) -> list[dict]:
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
        published = parse_date(child_text(entry, "pubDate", f"{ATOM}published", f"{ATOM}updated", f"{DC}date"))
        if not published:
            continue
        description = child_text(entry, "description", f"{ATOM}summary", f"{ATOM}content")
        summary = clean_text(description, 280)
        if summary.casefold() == title.casefold():
            summary = ""
        result.append({
            "id": hashlib.sha256(link.encode("utf-8")).hexdigest()[:20],
            "title": title,
            "url": link,
            "summary": summary,
            "publishedAt": published,
            "sourceIds": [source["id"]],
        })
    return result


def title_key(article: dict) -> str:
    return re.sub(r"[^\w가-힣]", "", article["title"].casefold())


def link_quality(url: str) -> int:
    host = urllib.parse.urlsplit(url).hostname or ""
    return 0 if host in AGGREGATOR_HOSTS else 1


def merge_articles(old: list[dict], incoming: list[dict], source_order: list[str]) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    valid = []
    for article in old + incoming:
        try:
            known_sources = [source_id for source_id in article["sourceIds"] if source_id in source_order]
            if known_sources and datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00")) >= cutoff:
                valid.append({**article, "sourceIds": known_sources})
        except (KeyError, ValueError):
            continue
    valid.sort(key=lambda item: item["publishedAt"], reverse=True)
    merged: list[dict] = []
    by_url: dict[str, dict] = {}
    by_title: dict[str, list[dict]] = {}
    for article in valid:
        key = title_key(article)
        match = by_url.get(article["url"])
        if not match and len(key) >= 20:
            for candidate in by_title.get(key, []):
                left = datetime.fromisoformat(candidate["publishedAt"].replace("Z", "+00:00"))
                right = datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00"))
                if abs(left - right) <= timedelta(days=2):
                    match = candidate
                    break
        if match:
            match["sourceIds"] = sorted(set(match["sourceIds"] + article["sourceIds"]), key=source_order.index)
            if link_quality(article["url"]) > link_quality(match["url"]):
                match["url"] = article["url"]
            if not match.get("summary") and article.get("summary"):
                match["summary"] = article["summary"]
            by_url[article["url"]] = match
        else:
            copied = {key: article[key] for key in ("id", "title", "url", "summary", "publishedAt", "sourceIds")}
            copied["sourceIds"] = [source_id for source_id in source_order if source_id in copied["sourceIds"]]
            merged.append(copied)
            by_url[copied["url"]] = copied
            by_title.setdefault(key, []).append(copied)
    return merged[:MAX_ARTICLES]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-all", action="store_true", help="Fail if any feed fails")
    args = parser.parse_args()
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    old_doc = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"articles": []}
    incoming: list[dict] = []
    failures = []
    for source in sources:
        try:
            entries = entries_from(fetch_xml(source["url"]), source)
            if not entries:
                raise ValueError("no usable entries")
            incoming.extend(entries)
            print(f"{source['name']}: {len(entries)} entries")
        except Exception as exc:
            failures.append(source["id"])
            print(f"{source['name']}: {exc}", file=sys.stderr)
    if not incoming or (args.require_all and failures):
        return 1
    merged = merge_articles(old_doc.get("articles", []), incoming, [source["id"] for source in sources])
    if merged != old_doc.get("articles", []) or old_doc.get("sources") != sources:
        document = {
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
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
