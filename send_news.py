import os
import re
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import feedparser


DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

FEEDS = [
    (
        "Rocket League Official",
        "https://news.google.com/rss/search?q=Rocket+League+site%3Arocketleague.com%2Fen%2Fnews&hl=en-US&gl=US&ceid=US%3Aen",
    ),
    (
        "Rocket League Esports",
        "https://news.google.com/rss/search?q=Rocket+League+esports+RLCS&hl=en-US&gl=US&ceid=US%3Aen",
    ),
    (
        "Players & Teams",
        "https://news.google.com/rss/search?q=Rocket+League+player+team+roster+transfer+signing&hl=en-US&gl=US&ceid=US%3Aen",
    ),
    (
        "Tournaments",
        "https://news.google.com/rss/search?q=Rocket+League+tournament+Major+Worlds+Regional&hl=en-US&gl=US&ceid=US%3Aen",
    ),
    (
        "Updates",
        "https://news.google.com/rss/search?q=Rocket+League+update+patch+season+Psyonix&hl=en-US&gl=US&ceid=US%3Aen",
    ),
]


KEYWORDS = [
    "rocket league",
    "rlcs",
    "psyonix",
    "rocket league esports",
    "rocket league championship series",
    "rocket league major",
    "rocket league worlds",
    "rocket league regional",
    "rocket league roster",
    "rocket league transfer",
    "rocket league player",
    "rocket league team",
    "rocket league organization",
    "rocket league tournament",
    "rocket league update",
    "rocket league patch",
    "rocket league season",
    "rocket league coach",
]


BLOCKED = [
    "rocket league sideswipe",
]


MAX_ARTICLES = 8

HISTORY_FILE = "data/sent.json"

HISTORY_LIMIT = 300


def clean(value):
    value = re.sub(r"<[^>]+>", "", value or "")
    return re.sub(r"\s+", " ", value).strip()


def relevant(entry):

    title = clean(entry.get("title", "")).lower()
    summary = clean(entry.get("summary", "")).lower()

    text = f"{title} {summary}"

    if any(term in text for term in BLOCKED):
        return False

    return any(term in text for term in KEYWORDS)


def get_source(link, fallback):

    try:
        host = urlparse(link).netloc.lower()
        host = host.replace("www.", "")

        return host or fallback

    except Exception:
        return fallback


def load_history():

    try:

        with open(HISTORY_FILE, "r", encoding="utf-8") as file:

            return set(json.load(file))

    except (FileNotFoundError, json.JSONDecodeError):

        return set()


def save_history(history):

    history = list(history)[-HISTORY_LIMIT:]

    with open(HISTORY_FILE, "w", encoding="utf-8") as file:

        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2
        )


def get_articles():

    articles = []

    seen = set()

    for feed_name, feed_url in FEEDS:

        try:

            feed = feedparser.parse(feed_url)

            for entry in feed.entries:

                if not relevant(entry):
                    continue

                link = entry.get("link", "").strip()

                title = clean(
                    entry.get("title", "")
                )

                key = link or title.lower()

                if not key:
                    continue

                if key in seen:
                    continue

                seen.add(key)

                articles.append(
                    (
                        entry,
                        feed_name
                    )
                )

        except Exception as error:

            print(
                f"[WARNING] Feed failed: {feed_name}: {error}"
            )

    return articles


def get_timestamp(entry):

    return (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
        or ()
    )


def create_discord_payload(
    entry,
    feed_name
):

    title = clean(
        entry.get(
            "title",
            "Rocket League News"
        )
    )

    description = clean(
        entry.get(
            "summary",
            "خبر جديد متعلق بـ Rocket League."
        )
    )

    if len(title) > 256:

        title = title[:253] + "..."

    if len(description) > 300:

        description = (
            description[:297]
            + "..."
        )

    link = entry.get(
        "link",
        ""
    ).strip()

    payload = {

        "username":
            "GGNews Rocket League",

        "embeds": [

            {

                "title": title,

                "url": link,

                "description":
                    description,

                "color":
                    0x2F80ED,

                "fields": [

                    {

                        "name":
                            "المصدر",

                        "value":
                            get_source(
                                link,
                                feed_name
                            ),

                        "inline":
                            True
                    },

                    {

                        "name":
                            "التصنيف",

                        "value":
                            "Rocket League",

                        "inline":
                            True
                    }

                ],

                "footer": {

                    "text":
                        "GGNews • Rocket League"

                },

                "timestamp":
                    datetime.now(
                        timezone.utc
                    ).isoformat()

            }

        ]

    }

    return payload


def send_to_discord(payload):

    response = requests.post(

        DISCORD_WEBHOOK_URL,

        json=payload,

        params={
            "wait": "true"
        },

        timeout=20

    )

    response.raise_for_status()


def main():

    print(
        "Starting Rocket League News..."
    )

    history = load_history()

    articles = get_articles()

    new_articles = []

    for entry, feed_name in articles:

        link = entry.get(
            "link",
            ""
        ).strip()

        key = (
            link
            or clean(
                entry.get(
                    "title",
                    ""
                )
            ).lower()
        )

        if key not in history:

            new_articles.append(
                (
                    entry,
                    feed_name,
                    key
                )
            )

    new_articles.sort(
        key=lambda article:
            get_timestamp(
                article[0]
            )
    )

    new_articles = new_articles[
        -MAX_ARTICLES:
    ]

    published = 0

    for entry, feed_name, key in new_articles:

        try:

            payload = create_discord_payload(
                entry,
                feed_name
            )

            send_to_discord(
                payload
            )

            history.add(key)

            published += 1

            print(
                "Published:",
                entry.get("title")
            )

        except Exception as error:

            print(
                "[ERROR]",
                error
            )

    save_history(history)

    print(
        f"Published {published} new articles."
    )


if __name__ == "__main__":

    main()
