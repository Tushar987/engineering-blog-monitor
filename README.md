# Engineering Blog Monitor

Daily poller for 15 top engineering blogs (Netflix, Uber, Cloudflare, Stripe, Meta, Airbnb, AWS, Google, ByteByteGo, High Scalability, Martin Fowler, LinkedIn, Discord, Shopify, Slack) — sends one Discord message per new post and publishes an aggregated dashboard to GitHub Pages.

## 📰 Live dashboard

The aggregated blog feed is hosted on GitHub Pages from this repository:

**👉 https://tushar987.github.io/engineering-blog-monitor/**

It updates daily from the `/docs` folder on `main` whenever the workflow finds new posts.

## 💬 Get the Discord notifications

Every new post triggers a Discord embed in a public channel — join to get pinged whenever one of the 15 engineering blogs publishes:

**👉 https://discord.gg/xNW33RRhrq**

(Make sure server notifications are set to **All Messages** if you want every post.)

## How it works

```
GitHub Actions (daily 13:07 UTC)
        │
        ▼
   monitor.py  ──▶ fetch RSS feeds (feedparser)
                ──▶ diff against state.json (seen ids)
                ──▶ Discord webhook per new post
                ──▶ regenerate posts.json + docs/index.html
        │
        ▼
   commit back to repo → GitHub Pages serves docs/
```

State (`state.json`, `posts.json`) lives in the repo. No database.

## One-time setup

### 1. Create a Discord webhook

1. In Discord, open the server + channel where you want notifications.
2. Channel name → **Edit Channel** (gear icon) → **Integrations** → **Webhooks** → **New Webhook**.
3. Name it `Engineering Blog Monitor`, click **Copy Webhook URL**.

### 2. Push to GitHub and add the secret

```sh
cd ~/CODE/GitHub/engineering-blog-monitor
git init -b main
git add .
git commit -m "initial commit"
gh repo create engineering-blog-monitor --public --source=. --push
```

Then add the webhook URL as a repo secret:

- **Settings → Secrets and variables → Actions → New repository secret**
- Name: `DISCORD_WEBHOOK_URL`
- Value: (the URL you copied)

### 3. Enable GitHub Pages

- **Settings → Pages**
- Source: **Deploy from a branch**, Branch: **main**, Folder: **/docs**

Dashboard will be live at `https://<your-username>.github.io/engineering-blog-monitor/`.

### 4. Run it once

From the **Actions** tab, pick **Monitor engineering blogs** → **Run workflow**. The first run seeds state silently (no Discord spam). The next run, and every daily run thereafter, sends one Discord embed per new post.

## Local development

```sh
pip install -r requirements.txt

# Dry-run: fetch all feeds, log counts, write nothing
python monitor.py --dry-run

# Real run (no DISCORD_WEBHOOK_URL set → silent first-run seed)
python monitor.py

# Test notifications: set env, delete one id from state.json, re-run
export DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...'
python monitor.py

# Preview dashboard
open docs/index.html
```

## Files

| File | Purpose |
|---|---|
| `feeds.yaml` | 15 blogs: name, site_url, feed_url, tagline |
| `monitor.py` | Main entry: fetch → diff → notify → render |
| `discord_notify.py` | Discord webhook helper (rich embeds) |
| `render.py` | Builds `docs/index.html` from `posts.json` |
| `templates/index.html.j2` | Jinja2 template for the dashboard |
| `docs/style.css` | Dark-theme styling, no framework |
| `state.json` | `{feed_url: [seen_entry_ids]}` (generated) |
| `posts.json` | All aggregated posts, newest first (generated) |
| `docs/index.html` | Public dashboard (generated) |
| `.github/workflows/monitor.yml` | Daily cron + commit-back |

## Tweaking

- **Polling cadence**: change the cron in `.github/workflows/monitor.yml`.
- **Add/remove a blog**: edit `feeds.yaml`. To force a silent re-seed for a feed, delete its key from `state.json`.
- **Notification format**: edit `_build_embed` in `discord_notify.py`.
- **Dashboard styling**: `docs/style.css` + `templates/index.html.j2`.

## Known limitations

- **LinkedIn Engineering** and **Discord Engineering** may not expose stable RSS. If those feeds fail to parse, they show up in the run summary as "Failed feeds". Fix: replace the `feed_url` with a working one or add a small scraper.
- RSS feeds typically expose only the latest ~10–25 posts, so the dashboard reflects recent history per blog, not full archives.
