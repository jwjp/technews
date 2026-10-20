#!/usr/bin/env python3
"""Apply an owner-created GitHub issue to the shared RSS source list."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from discover_sources import CATALOG, MAX_FEED_BYTES, candidate_id, fetch_bytes, normalized_feed, safe_http_url
from fetch_feeds import ATOM, ROOT, SOURCES


def request_from_event(event: dict, repository: str) -> tuple[str, str]:
    owner = repository.split("/", 1)[0]
    issue = event.get("issue", {})
    if event.get("action") != "opened" or not owner or issue.get("user", {}).get("login", "").casefold() != owner.casefold():
        raise ValueError("Only new issues from the repository owner can change subscriptions")
    title = issue.get("title", "")
    body = (issue.get("body") or "").strip()
    if title.startswith("[구독] "):
        match = re.fullmatch(r"candidate_id: ([0-9a-f]{16})", body)
        if match:
            return "subscribe", match.group(1)
    if title.startswith("[구독 해제] "):
        match = re.fullmatch(r"source_id: ([A-Za-z0-9][A-Za-z0-9_-]{0,79})", body)
        if match:
            return "unsubscribe", match.group(1)
    raise ValueError("Issue title or source ID is not a valid subscription request")


def source_from_candidate(candidate: dict) -> dict:
    feed_url = safe_http_url(candidate.get("feedUrl", ""))
    if not feed_url or candidate.get("id") != candidate_id(feed_url):
        raise ValueError("Candidate RSS address does not match its ID")
    section, kind = candidate.get("section"), candidate.get("kind")
    if section not in {"tech", "economy"} or kind not in {"blog", "news", "policy"}:
        raise ValueError("Candidate category is invalid")
    if not isinstance(candidate.get("name"), str) or not candidate["name"].strip():
        raise ValueError("Candidate name is missing")
    root = ET.fromstring(fetch_bytes(feed_url, MAX_FEED_BYTES))
    if root.tag not in {"rss", f"{ATOM}feed"}:
        raise ValueError("Candidate URL no longer returns an RSS or Atom feed")
    group = ("추가한 기술 블로그" if kind == "blog" else "추가한 기술 뉴스") if section == "tech" else ("추가한 경제 블로그" if kind == "blog" else "추가한 경제 뉴스")
    source = {"id": f"candidate-{candidate['id']}", "name": candidate["name"].strip()[:90], "url": feed_url, "group": group}
    if section == "economy":
        source["type"] = "economy-blog" if kind == "blog" else "economy"
    elif kind != "blog":
        source["type"] = "news"
    if kind != "blog":
        source["classify"] = True
    return source


def apply_request(action: str, identifier: str, sources: list[dict], catalog: list[dict]) -> tuple[list[dict], str]:
    if action == "subscribe":
        candidate = next((item for item in catalog if item.get("id") == identifier), None)
        if candidate is None:
            raise ValueError("Candidate is not in the verified source catalog")
        feed_url = safe_http_url(candidate.get("feedUrl", ""))
        if not feed_url or candidate.get("id") != candidate_id(feed_url):
            raise ValueError("Candidate RSS address does not match its ID")
        if any(normalized_feed(item["url"]) == normalized_feed(feed_url) for item in sources):
            return sources, "already-subscribed"
        source = source_from_candidate(candidate)
        if any(item["id"] == source["id"] for item in sources):
            raise ValueError("Source ID is already in use")
        return sources + [source], "subscribed"
    if action == "unsubscribe":
        remaining = [item for item in sources if item["id"] != identifier]
        return (remaining, "unsubscribed") if len(remaining) != len(sources) else (sources, "already-unsubscribed")
    raise ValueError("Unknown subscription action")


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not event_path or not repository:
        raise ValueError("GitHub issue event and repository are required")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    action, identifier = request_from_event(event, repository)
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8")).get("sources", [])
    updated, result = apply_request(action, identifier, sources, catalog)
    changed = updated != sources
    if changed:
        SOURCES.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"changed={'true' if changed else 'false'}\nresult={result}\n")
    print(f"Subscription request: {result} ({identifier})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, ET.ParseError) as exc:
        print(f"Subscription request rejected: {exc}", file=sys.stderr)
        raise SystemExit(1)
