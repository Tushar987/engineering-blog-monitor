"""Render docs/index.html from posts.json + feeds.yaml using Jinja2."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
TEMPLATE_DIR = ROOT / "templates"
OUTPUT = ROOT / "docs" / "index.html"


def render(posts_path: Path, feeds_path: Path, output_path: Path = OUTPUT) -> None:
    with posts_path.open() as f:
        posts = json.load(f)
    with feeds_path.open() as f:
        feeds = yaml.safe_load(f)

    blog_sites = {f["name"]: f["site_url"] for f in feeds}
    blogs = [f["name"] for f in feeds]

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    # Embed posts as a JSON string the client JS parses.
    # `</script>` inside JSON would break the surrounding <script> tag, so escape it.
    posts_json = json.dumps(posts, ensure_ascii=False).replace("</", "<\\/")

    template = env.get_template("index.html.j2")
    html = template.render(
        posts=posts,
        posts_json=posts_json,
        blogs=blogs,
        blog_sites=blog_sites,
        blog_count=len(blogs),
        post_count=len(posts),
        last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
