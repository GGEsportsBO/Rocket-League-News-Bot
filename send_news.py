import os
import re
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import feedparser

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

FEEDS = [
    ("Rocket League Official", "https://news.google.com/rss/search?q=Rocket+League+site%3Arocketleague.com%2Fen%2Fnews&hl=en-US&gl=US&ceid=US%3Aen"),
    ("Rocket League Esports", "https://news.google.com/rss/search?q=Rocket+League+esports+RLCS&hl=en-US&gl=US&ceid=US%3Aen"),
    ("Players & Teams", "https://news.google.com/rss/search?q=Rocket+League+player+team+roster+transfer+signing&hl=en-US&gl=US&ceid=US%3Aen"),
    ("Tournaments", "https://news.google.com/rss/search?q=Rocket+League+tournament+Major+Worlds+Regional&hl=en-US&gl=US&ceid=US%3Aen"),
    ("Updates", "https://news.google.com/rss/search?q=Rocket+League+update+patch+season+Psyonix&hl=en-US&gl=US&ceid=US%3Aen"),
]

KEYWORDS = [
    "rocket league", "rlcs", "psyonix", "rocket league esports",
    "rocket league championship series", "rocket league major",
    "rocket league worlds", "rocket league regional", "rocket league roster",
    "rocket league transfer", "rocket league player", "rocket league team",
    "rocket league organization", "rocket league tournament",
    "rocket league update", "rocket league patch", "rocket league season",
    "rocket league coach",
]

BLOCKED = ["rocket league sideswipe"]

MAX_ARTICLES = 8
HISTORY_FILE = "data/sent.json"
HISTORY_LIMIT = 300


def clean(value):
    value = re.sub(r"<[^>]+>", "", value or "")
    return re.sub(r"\s+", " ", value).strip()


def relevant(entry):
    text = f"{clean(entry.get('title')).lower()} {clean(entry.get('summary')).lower()}"
    return not any(x in text for x in BLOCKED) and any(x in text for x in KEYWORDS)


def source(link, fallback):
    host = urlparse(link).netloc.lower().replace("www.", "")
    return host or fallback


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_history(history):
    trimmed = list(history)[-HISTORY_LIMIT:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def fetch():
    articles = []
    seen = set()

    for feed_name, url in FEEDS:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries:
                if not relevant(entry):
                    continue

                link = entry.get("link", "").strip()
                title = clean(entry.get("title", ""))
                key = link or title.lower()

                if not key or key in seen:
                    continue

                seen.add(key)
                articles.append((entry, feed_name))
        except Exception as exc:
            print(f"[WARN] Feed failed: {feed_name}: {exc}")

    return articles


def timestamp(entry):
    return entry.get("published_parsed") or entry.get("updated_parsed")


def build_payload(entry, feed_name):
    title = clean(entry.get("title", "Rocket League News"))[:256]
    description = clean(entry.get("summary", "خبر جديد متعلق بـ Rocket League."))
    if len(description) > 300:
        description = description[:297].rstrip() + "..."

    link = entry.get("link", "").strip()

    return {
        "username": "Rocket League News",
        "embeds": [{
            "title": title,
            "url": link,
            "description": description,
            "color": 0x2F80ED,
            "fields": [
                {
                    "name": "المصدر",
                    "value": source(link, feed_name),
                    "inline": True,
                },
                {
                    "name": "التصنيف",
                    "value": "Rocket League",
                    "inline": True,
                },
            ],
            "footer": {
                "text": "GGNews • Rocket League"
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }


def send(payload):
    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=20,
        params={"wait": "true"},
    )
    response.raise_for_status()


def main():
    history = load_history()
    articles = fetch()

    new_articles = []
    for entry, feed_name in articles:
        link = entry.get("link", "").strip()
        key = link or clean(entry.get("title", "")).lower()
        if key not in history:
            new_articles.append((entry, feed_name, key))

    # Publish oldest first.
    new_articles.sort(key=lambda x: timestamp(x[0]) or ())

    published = 0
    for entry, feed_name, key in new_articles[-MAX_ARTICLES:]:
        try:
            send(build_payload(entry, feed_name))
            history.add(key)
            published += 1
        except Exception as exc:
            print(f"[ERROR] Discord webhook failed: {exc}")

    save_history(history)
    print(f"Published {published} new Rocket League articles.")


if __name__ == "__main__":
    main()
