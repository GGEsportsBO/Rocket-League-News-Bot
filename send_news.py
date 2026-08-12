import os
import re
import json
import time
import calendar
import requests
import feedparser

from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse


# =========================================================
# CONFIG
# =========================================================

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_MODEL = "gemini-3.1-flash-lite"

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent"
)

NEWS_WINDOW_HOURS = 24

MAX_ARTICLES_PER_RUN = 10

HISTORY_FILE = "data/sent.json"

HISTORY_LIMIT = 500


# =========================================================
# NEWS SEARCHES
# =========================================================

FEEDS = [

    (
        "Rocket League Official",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+site%3Arocketleague.com%2Fnews+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Competitive",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+site%3Arocketleague.com%2Fcompetitive+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "RLCS",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+RLCS+2026+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Transfers",
        "https://news.google.com/rss/search?"
        "q=%22Rocket+League%22+transfer+roster+signing+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Players",
        "https://news.google.com/rss/search?"
        "q=%22Rocket+League%22+player+retirement+announcement+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Teams",
        "https://news.google.com/rss/search?"
        "q=%22Rocket+League%22+team+organization+roster+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Tournaments",
        "https://news.google.com/rss/search?"
        "q=%22Rocket+League%22+tournament+Major+Worlds+Regional+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Esports",
        "https://news.google.com/rss/search?"
        "q=%22Rocket+League%22+esports+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Competitive News",
        "https://news.google.com/rss/search?"
        "q=%22Rocket+League%22+RLCS+esports+news+when%3A1d"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

]


# =========================================================
# KEYWORDS
# =========================================================

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
    "rocket league signing",

    "rocket league player",
    "rocket league team",
    "rocket league organization",

    "rocket league tournament",

    "rocket league update",
    "rocket league patch",
    "rocket league season",

    "rocket league coach",

    "rlcs 2026",

]


BLOCKED_KEYWORDS = [

    "rocket league sideswipe",

]


# =========================================================
# TEXT
# =========================================================

def clean_text(value):

    value = value or ""

    value = re.sub(
        r"<[^>]+>",
        "",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# =========================================================
# DATE
# =========================================================

def get_article_datetime(entry):

    parsed = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
    )

    if not parsed:

        return None

    try:

        timestamp = calendar.timegm(
            parsed
        )

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        )

    except Exception:

        return None


def is_last_24_hours(entry):

    article_date = get_article_datetime(
        entry
    )

    if article_date is None:

        return False

    now = datetime.now(
        timezone.utc
    )

    age = now - article_date

    if age.total_seconds() < 0:

        return False

    if age > timedelta(
        hours=NEWS_WINDOW_HOURS
    ):

        return False

    return True


def age_text(entry):

    article_date = get_article_datetime(
        entry
    )

    if not article_date:

        return "غير معروف"

    now = datetime.now(
        timezone.utc
    )

    minutes = int(
        (now - article_date)
        .total_seconds()
        / 60
    )

    if minutes < 60:

        return f"{minutes} دقيقة"

    hours = minutes // 60

    if hours == 1:

        return "ساعة"

    return f"{hours} ساعة"


# =========================================================
# SOURCE
# =========================================================

def get_source(link, fallback):

    try:

        host = urlparse(
            link
        ).netloc.lower()

        host = host.replace(
            "www.",
            ""
        )

        return host or fallback

    except Exception:

        return fallback


# =========================================================
# RELEVANCE
# =========================================================

def is_relevant(entry):

    title = clean_text(
        entry.get(
            "title",
            ""
        )
    ).lower()

    summary = clean_text(
        entry.get(
            "summary",
            ""
        )
    ).lower()

    text = (
        title
        + " "
        + summary
    )

    for blocked in BLOCKED_KEYWORDS:

        if blocked in text:

            return False

    for keyword in KEYWORDS:

        if keyword in text:

            return True

    return False


# =========================================================
# HISTORY
# =========================================================

def load_history():

    try:

        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return set(
                json.load(file)
            )

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        return set()


def save_history(history):

    history = list(history)

    history = history[
        -HISTORY_LIMIT:
    ]

    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# DISCORD WEBHOOK CHECK
# =========================================================

def verify_webhook():

    print(
        "[DISCORD] Checking webhook..."
    )

    try:

        response = requests.get(
            DISCORD_WEBHOOK_URL,
            timeout=15
        )

        if response.status_code == 200:

            print(
                "[DISCORD] Webhook is valid."
            )

            return True

        print(
            f"[DISCORD ERROR] "
            f"Webhook returned HTTP "
            f"{response.status_code}"
        )

        print(
            response.text[:500]
        )

        return False

    except Exception as error:

        print(
            f"[DISCORD ERROR] {error}"
        )

        return False


# =========================================================
# RSS
# =========================================================

def fetch_articles():

    articles = []

    seen = set()

    for feed_name, feed_url in FEEDS:

        print(
            f"[RSS] Checking: "
            f"{feed_name}"
        )

        try:

            response = requests.get(
                feed_url,
                headers={
                    "User-Agent":
                        "GGNews-RocketLeague/1.0"
                },
                timeout=20
            )

            response.raise_for_status()

            feed = feedparser.parse(
                response.content
            )

            feed_count = 0

            for entry in feed.entries:

                title = clean_text(
                    entry.get(
                        "title",
                        ""
                    )
                )

                link = entry.get(
                    "link",
                    ""
                ).strip()

                # -----------------------------------------
                # Rocket League filter
                # -----------------------------------------

                if not is_relevant(
                    entry
                ):

                    continue

                # -----------------------------------------
                # 24 hour filter
                # -----------------------------------------

                if not is_last_24_hours(
                    entry
                ):

                    continue

                # -----------------------------------------
                # Unique
                # -----------------------------------------

                key = (
                    link
                    or title.lower()
                )

                if not key:

                    continue

                if key in seen:

                    continue

                seen.add(
                    key
                )

                articles.append(
                    (
                        entry,
                        feed_name
                    )
                )

                feed_count += 1

            print(
                f"[RSS] {feed_name}: "
                f"{feed_count} valid articles"
            )

        except Exception as error:

            print(
                f"[RSS ERROR] "
                f"{feed_name}: "
                f"{error}"
            )

    return articles


# =========================================================
# GEMINI
# =========================================================

SYSTEM_PROMPT = """
أنت محرر أخبار Rocket League لمنصة GGNews.

حوّل المادة الإنجليزية إلى خبر عربي صحفي قصير ودقيق.

القواعد:

- لا تخترع أي معلومة.
- لا تضف أي أسماء أو نتائج أو أرقام غير موجودة.
- لا تقدم رأياً.
- لا تستخدم ترجمة حرفية.
- استخدم العربية الصحفية الحديثة.
- أسماء اللاعبين والفرق والمنظمات تبقى بالإنجليزية.
- Rocket League تكتب Rocket League.
- RLCS تكتب RLCS.
- العنوان مختصر ومباشر.
- الملخص من 2 إلى 4 جمل.
- إذا كان الخبر عن انتقال صنفه transfer.
- إذا كان عن لاعب صنفه player.
- إذا كان عن فريق صنفه team.
- إذا كان عن بطولة صنفه tournament.
- إذا كان عن نتيجة صنفه result.
- إذا كان عن تحديث للعبة صنفه update.
- إذا كان عن RLCS صنفه rlcs.
- إذا كان عن منظمة صنفه organization.
- إذا كان شائعة صنفه rumor.
- غير ذلك general.

الأهمية:

1 = منخفض
2 = عادي
3 = مهم
4 = مهم جداً
5 = عاجل أو خبر كبير جداً

أخرج JSON فقط:

{
  "headline": "...",
  "summary": "...",
  "category": "general",
  "importance": 2,
  "tags": ["Rocket League"]
}
"""


def ask_gemini(
    title,
    summary,
    source,
    link
):

    user_prompt = f"""
المصدر:
{source}

الرابط:
{link}

العنوان الأصلي:
{title}

المادة:
{summary}
"""

    payload = {

        "system_instruction": {

            "parts": [

                {
                    "text":
                        SYSTEM_PROMPT
                }

            ]

        },

        "contents": [

            {

                "parts": [

                    {
                        "text":
                            user_prompt
                    }

                ]

            }

        ],

        "generationConfig": {

            "responseMimeType":
                "application/json",

            "maxOutputTokens":
                500

        }

    }

    response = requests.post(

        GEMINI_URL,

        headers={

            "Content-Type":
                "application/json",

            "x-goog-api-key":
                GEMINI_API_KEY

        },

        json=payload,

        timeout=40

    )

    response.raise_for_status()

    data = response.json()

    text = (
        data
        ["candidates"][0]
        ["content"]["parts"][0]
        ["text"]
    )

    return json.loads(
        text
    )


# =========================================================
# FALLBACK
# =========================================================

def fallback_article(entry):

    return {

        "headline":
            clean_text(
                entry.get(
                    "title",
                    "Rocket League News"
                )
            ),

        "summary":
            clean_text(
                entry.get(
                    "summary",
                    ""
                )
            )[:800],

        "category":
            "general",

        "importance":
            2,

        "tags":
            [
                "Rocket League"
            ]

    }


# =========================================================
# DISCORD DESIGN
# =========================================================

CATEGORY_INFO = {

    "player":
        ("👤", "لاعب"),

    "team":
        ("🏢", "فريق"),

    "transfer":
        ("🔄", "انتقالات"),

    "tournament":
        ("🏆", "بطولة"),

    "result":
        ("📊", "نتائج"),

    "update":
        ("🎮", "تحديث"),

    "rlcs":
        ("🏆", "RLCS"),

    "organization":
        ("🏢", "منظمة"),

    "rumor":
        ("⚠️", "شائعة"),

    "general":
        ("📰", "عام"),

}


CATEGORY_COLORS = {

    "player":
        0x3498DB,

    "team":
        0x9B59B6,

    "transfer":
        0xF1C40F,

    "tournament":
        0xE67E22,

    "result":
        0x2ECC71,

    "update":
        0x1ABC9C,

    "rlcs":
        0xE74C3C,

    "organization":
        0x8E44AD,

    "rumor":
        0x95A5A6,

    "general":
        0x2F80ED,

}


IMPORTANCE = {

    1: "منخفضة",
    2: "عادية",
    3: "مهمة",
    4: "مهمة جداً",
    5: "عاجلة",

}


def create_payload(
    entry,
    feed_name,
    article
):

    category = article.get(
        "category",
        "general"
    )

    if category not in CATEGORY_INFO:

        category = "general"

    emoji, category_name = (
        CATEGORY_INFO[
            category
        ]
    )

    try:

        importance = int(
            article.get(
                "importance",
                2
            )
        )

    except Exception:

        importance = 2

    importance = max(
        1,
        min(
            5,
            importance
        )
    )

    headline = clean_text(
        article.get(
            "headline",
            entry.get(
                "title",
                "Rocket League News"
            )
        )
    )

    summary = clean_text(
        article.get(
            "summary",
            ""
        )
    )

    link = entry.get(
        "link",
        ""
    ).strip()

    source = get_source(
        link,
        feed_name
    )

    tags = article.get(
        "tags",
        []
    )

    if not isinstance(
        tags,
        list
    ):

        tags = [
            "Rocket League"
        ]

    fields = [

        {
            "name":
                "التصنيف",

            "value":
                f"{emoji} {category_name}",

            "inline":
                True
        },

        {
            "name":
                "الأهمية",

            "value":
                IMPORTANCE[
                    importance
                ],

            "inline":
                True
        },

        {
            "name":
                "عمر الخبر",

            "value":
                age_text(
                    entry
                ),

            "inline":
                True
        },

        {
            "name":
                "المصدر",

            "value":
                source,

            "inline":
                False
        }

    ]

    if tags:

        fields.append(

            {
                "name":
                    "الوسوم",

                "value":
                    " • ".join(
                        str(x)
                        for x in tags[:6]
                    ),

                "inline":
                    False
            }

        )

    embed = {

        "title":
            headline[:256],

        "url":
            link,

        "description":
            summary[:1000],

        "color":
            CATEGORY_COLORS[
                category
            ],

        "fields":
            fields,

        "footer":
            {
                "text":
                    "GGNews • Rocket League"
            },

        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat()

    }

    return {

        "username":
            "GGNews Rocket League",

        "embeds":
            [embed]

    }


def send_to_discord(
    payload
):

    response = requests.post(

        DISCORD_WEBHOOK_URL,

        params={
            "wait":
                "true"
        },

        json=payload,

        timeout=20

    )

    if response.status_code not in (
        200,
        204
    ):

        raise RuntimeError(
            f"Discord HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=========================================="
    )

    print(
        "GGNEWS ROCKET LEAGUE NEWS ENGINE"
    )

    print(
        "Window: LAST 24 HOURS"
    )

    print(
        "Schedule: EVERY HOUR"
    )

    print(
        "=========================================="
    )


    # -----------------------------------------
    # Verify Discord without sending a message
    # -----------------------------------------

    if not verify_webhook():

        print(
            "[FATAL] Discord Webhook is not valid."
        )

        raise SystemExit(1)


    # -----------------------------------------
    # Load history
    # -----------------------------------------

    history = load_history()

    print(
        f"[HISTORY] "
        f"{len(history)} previously sent links"
    )


    # -----------------------------------------
    # Get news
    # -----------------------------------------

    articles = fetch_articles()

    print(
        f"[NEWS] "
        f"{len(articles)} articles "
        f"from the last 24 hours"
    )


    if not articles:

        print(
            "[NEWS] No valid new articles."
        )

        print(
            "[DONE] Nothing to publish."
        )

        save_history(
            history
        )

        return


    # -----------------------------------------
    # Remove duplicates
    # -----------------------------------------

    new_articles = []

    for entry, feed_name in articles:

        link = entry.get(
            "link",
            ""
        ).strip()

        title = clean_text(
            entry.get(
                "title",
                ""
            )
        )

        key = (
            link
            or title.lower()
        )

        if key in history:

            print(
                f"[DUPLICATE] {title}"
            )

            continue

        new_articles.append(
            (
                entry,
                feed_name,
                key
            )
        )


    print(
        f"[NEWS] "
        f"{len(new_articles)} new articles"
    )


    if not new_articles:

        print(
            "[DONE] All recent articles "
            "were already published."
        )

        return


    # -----------------------------------------
    # Oldest first
    # -----------------------------------------

    new_articles.sort(

        key=lambda item:
            get_article_datetime(
                item[0]
            )
            or datetime.min.replace(
                tzinfo=timezone.utc
            )

    )


    # -----------------------------------------
    # Max per run
    # -----------------------------------------

    new_articles = new_articles[
        -MAX_ARTICLES_PER_RUN:
    ]


    # -----------------------------------------
    # Process
    # -----------------------------------------

    published = 0


    for entry, feed_name, key in new_articles:

        title = clean_text(
            entry.get(
                "title",
                ""
            )
        )

        summary = clean_text(
            entry.get(
                "summary",
                ""
            )
        )

        link = entry.get(
            "link",
            ""
        ).strip()

        source = get_source(
            link,
            feed_name
        )


        print(
            "------------------------------------------"
        )

        print(
            f"[ARTICLE] {title}"
        )

        print(
            f"[AGE] {age_text(entry)}"
        )

        print(
            f"[SOURCE] {source}"
        )


        # -------------------------------------
        # Gemini
        # -------------------------------------

        try:

            print(
                "[GEMINI] Processing..."
            )

            article = ask_gemini(

                title=
                    title,

                summary=
                    summary,

                source=
                    source,

                link=
                    link

            )

            print(
                "[GEMINI] Success"
            )

        except Exception as error:

            print(
                f"[GEMINI ERROR] {error}"
            )

            # لا نسقط الخبر بالكامل
            # لكن نستخدم fallback

            article = fallback_article(
                entry
            )


        # -------------------------------------
        # Discord
        # -------------------------------------

        try:

            payload = create_payload(

                entry,

                feed_name,

                article

            )

            print(
                "[DISCORD] Sending..."
            )

            send_to_discord(
                payload
            )

            history.add(
                key
            )

            published += 1

            print(
                "[DISCORD] Published successfully"
            )

            time.sleep(
                1
            )

        except Exception as error:

            print(
                f"[DISCORD ERROR] {error}"
            )


    # -----------------------------------------
    # Save history
    # -----------------------------------------

    save_history(
        history
    )


    print(
        "=========================================="
    )

    print(
        f"Published: {published}"
    )

    print(
        f"Checked: {len(articles)}"
    )

    print(
        "==========================================" 
    )


if __name__ == "__main__":

    main()
