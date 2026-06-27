"""Engineering blog monitor.

Polls 15 RSS/Atom feeds, diffs against state.json, notifies Discord for new posts,
rebuilds posts.json and the static dashboard.

First-run guard: if a feed has no prior state, seed silently (no notifications).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import struct_time, mktime
from typing import Any

import feedparser
import yaml

import discord_notify
import render

ROOT = Path(__file__).parent
FEEDS_PATH = ROOT / "feeds.yaml"
STATE_PATH = ROOT / "state.json"
POSTS_PATH = ROOT / "posts.json"

USER_AGENT = "EngineeringBlogMonitor/1.0 (+https://github.com/)"
FETCH_TIMEOUT_SECS = 15
SEEN_PER_FEED_CAP = 200
POSTS_TOTAL_CAP = 500

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("monitor")


def load_feeds() -> list[dict[str, str]]:
    with FEEDS_PATH.open() as f:
        return yaml.safe_load(f)


def load_state() -> dict[str, list[str]]:
    if not STATE_PATH.exists():
        return {}
    with STATE_PATH.open() as f:
        return json.load(f)


def save_state(state: dict[str, list[str]]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def save_posts(posts: list[dict[str, Any]]) -> None:
    POSTS_PATH.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")


def entry_id(entry: Any) -> str:
    return getattr(entry, "id", None) or getattr(entry, "link", None) or ""


def parse_published(entry: Any) -> tuple[str, str]:
    """Return (ISO timestamp for sorting, human-readable date)."""
    parsed: struct_time | None = (
        getattr(entry, "published_parsed", None)
        or getattr(entry, "updated_parsed", None)
    )
    if parsed:
        dt = datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
        return dt.isoformat(), dt.strftime("%Y-%m-%d")
    raw = getattr(entry, "published", None) or getattr(entry, "updated", "")
    return "", raw or "unknown"


def clean_summary(entry: Any) -> str:
    raw = getattr(entry, "summary", "") or ""
    import re
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_feed(feed_url: str) -> Any:
    return feedparser.parse(
        feed_url,
        agent=USER_AGENT,
        request_headers={"Accept": "application/rss+xml, application/atom+xml, */*"},
    )


def process(dry_run: bool = False) -> int:
    feeds = load_feeds()
    state = load_state()
    is_first_run_overall = not STATE_PATH.exists()

    aggregated: list[dict[str, Any]] = []
    new_count = 0
    notified_count = 0
    failed_feeds: list[str] = []

    for feed in feeds:
        name = feed["name"]
        feed_url = feed["feed_url"]
        log.info("Fetching %s", name)

        parsed = fetch_feed(feed_url)
        if parsed.bozo and not parsed.entries:
            log.warning("  ! Failed to parse: %s (%s)", feed_url, getattr(parsed, "bozo_exception", ""))
            failed_feeds.append(name)
            continue
        if not parsed.entries:
            log.warning("  ! No entries: %s", feed_url)
            failed_feeds.append(name)
            continue

        log.info("  %d entries", len(parsed.entries))
        seen_ids = set(state.get(feed_url, []))
        feed_is_first_run = feed_url not in state
        feed_new_entries: list[dict[str, Any]] = []
        current_ids_in_order: list[str] = []

        for entry in parsed.entries:
            eid = entry_id(entry)
            if not eid:
                continue
            iso_ts, display = parse_published(entry)
            post = {
                "id": eid,
                "blog_name": name,
                "title": (getattr(entry, "title", "") or "(untitled)").strip(),
                "link": getattr(entry, "link", ""),
                "summary": clean_summary(entry)[:500],
                "published_iso": iso_ts,
                "published_display": display,
                "feed_url": feed_url,
            }
            aggregated.append(post)
            current_ids_in_order.append(eid)
            if eid not in seen_ids:
                feed_new_entries.append(post)

        if feed_is_first_run:
            log.info("  (first run for this feed — seeding %d ids silently)", len(current_ids_in_order))
        else:
            new_count += len(feed_new_entries)
            if feed_new_entries and not dry_run:
                for post in feed_new_entries:
                    log.info("  → notify: %s", post["title"][:80])
                    if discord_notify.notify(post):
                        notified_count += 1

        if not dry_run:
            combined_ids = current_ids_in_order + [i for i in state.get(feed_url, []) if i not in set(current_ids_in_order)]
            state[feed_url] = combined_ids[:SEEN_PER_FEED_CAP]

    aggregated.sort(key=lambda p: p["published_iso"], reverse=True)
    aggregated = aggregated[:POSTS_TOTAL_CAP]

    log.info("Summary: %d feeds, %d posts aggregated, %d new, %d notified, %d failed",
             len(feeds), len(aggregated), new_count, notified_count, len(failed_feeds))
    if failed_feeds:
        log.warning("Failed feeds (need attention): %s", ", ".join(failed_feeds))

    if dry_run:
        log.info("Dry run — no state, posts.json, or HTML written.")
        return 0

    save_state(state)
    save_posts(aggregated)
    render.render(POSTS_PATH, FEEDS_PATH)
    log.info("Wrote state.json, posts.json, docs/index.html")
    if is_first_run_overall:
        log.info("First-run seed complete — future runs will notify on new posts.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Fetch + diff but write nothing and skip Discord.")
    args = parser.parse_args()
    return process(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
