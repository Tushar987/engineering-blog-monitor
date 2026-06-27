"""Discord webhook notifier: one rich embed per new blog post."""
from __future__ import annotations

import os
import time
import logging
from typing import Any

import requests

log = logging.getLogger(__name__)

WEBHOOK_ENV = "DISCORD_WEBHOOK_URL"
RATE_LIMIT_SLEEP_SECS = 1.0
EMBED_COLOR = 5793266  # muted blue
DESCRIPTION_MAX = 300


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _build_embed(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "author": {"name": post["blog_name"]},
        "title": _truncate(post["title"], 250),
        "url": post["link"],
        "description": _truncate(post.get("summary", ""), DESCRIPTION_MAX),
        "footer": {"text": f"Published {post.get('published_display', 'unknown')} · Engineering Blog Monitor"},
        "color": EMBED_COLOR,
    }


def notify(post: dict[str, Any]) -> bool:
    """POST one embed to the configured Discord webhook.

    Returns True on success, False if webhook is unset (caller can decide).
    """
    webhook = os.environ.get(WEBHOOK_ENV)
    if not webhook:
        log.info("DISCORD_WEBHOOK_URL not set — skipping notify for %s", post["title"])
        return False

    payload = {"embeds": [_build_embed(post)]}
    resp = requests.post(webhook, json=payload, timeout=10)
    if resp.status_code >= 300:
        log.warning("Discord webhook returned %s: %s", resp.status_code, resp.text[:200])
    time.sleep(RATE_LIMIT_SLEEP_SECS)
    return resp.ok
