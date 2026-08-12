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
# ENVIRONMENT
# =========================================================

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_MODEL = "gemini-3.1-flash-lite"

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent"
)


# =========================================================
# SETTINGS
# =========================================================

# نفحص آخر 24 ساعة فقط
NEWS_WINDOW_HOURS = 24

# الحد الأقصى للأخبار في كل تشغيل
MAX_ARTICLES_PER_RUN = 6

# عدد الروابط المحفوظة لمنع التكرار
HISTORY_LIMIT = 500

HISTORY_FILE = "data/sent.json"


# =========================================================
# ROCKET LEAGUE SOURCES
# =========================================================

FEEDS = [

    (
        "Rocket League Official",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+site%3Arocketleague.com%2Fnews"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Competitive",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+site%3Arocketleague.com%2Fnews+competitive"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "RLCS",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+RLCS+Major+Worlds"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Players",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+player+announcement+transfer+retirement"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Teams",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+team+organization+roster+signing"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Tournaments",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+tournament+regional+major+final"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Updates",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+patch+update+season+Psyonix"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Liquipedia Rocket League",
        "https://news.google.com/rss/search?"
        "q=Rocket+League+site%3Aliquipedia.net%2Frocketleague"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),

    (
        "Rocket League Esports",
        "https://news.google.com/rss/search?"
        "q=%22Rocket+League%22+esports+roster+transfer"
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
# DATE / TIME
# =========================================================

def get_article_datetime(entry):

    """
    يحاول الحصول على تاريخ نشر الخبر.
    إذا لم يوجد، يحاول استخدام تاريخ التحديث.
    إذا لم يوجد أي تاريخ، يرجع None.
    """

    parsed_date = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
    )

    if not parsed_date:

        return None

    try:

        timestamp = calendar.timegm(
            parsed_date
        )

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        )

    except Exception:

        return None


def is_within_last_24_hours(entry):

    article_date = get_article_datetime(
        entry
    )

    # إذا الخبر لا يحتوي على تاريخ واضح
    # نتجاهله بدلاً من المخاطرة بإرسال خبر قديم
    if article_date is None:

        return False

    now = datetime.now(
        timezone.utc
    )

    age = now - article_date

    # الأخبار المستقبلية يتم تجاهلها
    if age.total_seconds() < 0:

        return False

    # أقدم من 24 ساعة = تجاهل
    if age > timedelta(
        hours=NEWS_WINDOW_HOURS
    ):

        return False

    return True


def article_age_text(entry):

    article_date = get_article_datetime(
        entry
    )

    if not article_date:

        return "Unknown"

    now = datetime.now(
        timezone.utc
    )

    age = now - article_date

    minutes = int(
        age.total_seconds() / 60
    )

    if minutes < 60:

        return f"{minutes} دقيقة"

    hours = minutes // 60

    return f"{hours} ساعة"


# =========================================================
# SOURCE
# =========================================================

def get_source(
    link,
    fallback
):

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
        f"{title} {summary}"
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
# RSS
# =========================================================

def fetch_articles():

    articles = []

    seen = set()

    for feed_name, feed_url in FEEDS:

        try:

            print(
                f"[RSS] Checking: {feed_name}"
            )

            feed = feedparser.parse(
                feed_url
            )

            for entry in feed.entries:

                # -----------------------------------------
                # 1. Rocket League relevance
                # -----------------------------------------

                if not is_relevant(
                    entry
                ):

                    continue

                # -----------------------------------------
                # 2. LAST 24 HOURS
                # -----------------------------------------

                if not is_within_last_24_hours(
                    entry
                ):

                    title = clean_text(
                        entry.get(
                            "title",
                            ""
                        )
                    )

                    print(
                        f"[OLD] Ignored: {title}"
                    )

                    continue

                # -----------------------------------------
                # 3. Unique in this run
                # -----------------------------------------

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

        except Exception as error:

            print(
                f"[RSS ERROR] "
                f"{feed_name}: {error}"
            )

    return articles


# =========================================================
# IMAGE
# =========================================================

def get_image(entry):

    try:

        if "media_content" in entry:

            for media in entry.media_content:

                url = media.get(
                    "url"
                )

                if url:

                    return url

        if "media_thumbnail" in entry:

            for media in entry.media_thumbnail:

                url = media.get(
                    "url"
                )

                if url:

                    return url

        if "enclosures" in entry:

            for enclosure in entry.enclosures:

                url = enclosure.get(
                    "href"
                )

                if url:

                    return url

    except Exception:

        pass

    return None


# =========================================================
# GEMINI
# =========================================================

SYSTEM_PROMPT = """
أنت محرر أخبار Rocket League لمنصة GGNews.

مهمتك تحويل الخبر الإنجليزي الخام إلى خبر عربي احترافي قصير
مناسب للنشر في Discord.

القواعد:

1. لا تخترع أي معلومة.
2. لا تضف أسماء أو أرقام أو نتائج غير موجودة في المادة الأصلية.
3. لا تقل "بحسب مصادر" إلا إذا كانت المادة نفسها تقول ذلك.
4. إذا كان الخبر مجرد شائعة، صنفه "rumor".
5. لا تقدم رأياً شخصياً.
6. لا تستخدم ترجمة حرفية ركيكة.
7. استخدم العربية الصحفية الحديثة.
8. اجعل العنوان جذاباً لكن دقيقاً.
9. حافظ على أسماء اللاعبين والفرق والمنظمات بالإنجليزية.
10. Rocket League تكتب هكذا: Rocket League.
11. RLCS تكتب هكذا: RLCS.
12. لا تستخدم إيموجيات داخل العنوان.
13. الملخص من 2 إلى 4 جمل فقط.
14. إذا كان الخبر متعلقاً بانتقال لاعب، ركز على اللاعب والفريق القديم والجديد إن كانت المعلومات متاحة.
15. إذا كان متعلقاً ببطولة، اذكر البطولة والنتيجة أو المرحلة إن كانت موجودة.
16. إذا كان Patch أو Update، اشرح أهم ما تغير فقط.
17. الأخبار الكبرى مثل انتقال لاعب بارز، نهائي Major، فوز بطولة، إعلان RLCS أو تحديث ضخم يمكن أن تكون importance = 5.

التصنيفات المسموحة:

player
team
transfer
tournament
result
update
rlcs
organization
rumor
general

الأهمية:

1 = منخفضة
2 = عادية
3 = مهمة
4 = مهمة جداً
5 = عاجلة / كبرى

أعد JSON فقط:

{
  "headline": "...",
  "summary": "...",
  "category": "player",
  "importance": 3,
  "tags": ["Rocket League", "RLCS"]
}
"""


def ask_gemini(
    title,
    summary,
    source,
    link
):

    prompt = f"""
المصدر:
{source}

الرابط:
{link}

العنوان الأصلي:
{title}

النص/الوصف:
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
                            prompt
                    }

                ]

            }

        ],

        "generationConfig": {

            "temperature":
                0.2,

            "maxOutputTokens":
                500,

            "responseMimeType":
                "application/json"

        }

    }

    headers = {

        "Content-Type":
            "application/json",

        "x-goog-api-key":
            GEMINI_API_KEY

    }

    response = requests.post(

        GEMINI_URL,

        headers=headers,

        json=payload,

        timeout=30

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

def fallback_article(
    entry
):

    return {

        "headline":
            clean_text(
                entry.get(
                    "title",
                    "أخبار Rocket League"
                )
            ),

        "summary":
            clean_text(
                entry.get(
                    "summary",
                    "خبر جديد متعلق بـ Rocket League."
                )
            )[:500],

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
# DISCORD
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


IMPORTANCE_INFO = {

    1: "منخفضة",
    2: "عادية",
    3: "مهمة",
    4: "مهمة جداً",
    5: "عاجلة",

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


def create_discord_payload(
    entry,
    feed_name,
    article
):

    category = article.get(
        "category",
        "general"
    )

    emoji, category_name = (
        CATEGORY_INFO.get(
            category,
            CATEGORY_INFO["general"]
        )
    )

    importance = int(
        article.get(
            "importance",
            2
        )
    )

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

    link = entry.get(
        "link",
        ""
    ).strip()

    source = get_source(
        link,
        feed_name
    )

    color = CATEGORY_COLORS.get(
        category,
        CATEGORY_COLORS["general"]
    )

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
                IMPORTANCE_INFO[
                    importance
                ],

            "inline":
                True
        },

        {
            "name":
                "عمر الخبر",

            "value":
                article_age_text(
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
        },

    ]

    if tags:

        fields.append(

            {
                "name":
                    "الوسوم",

                "value":
                    " • ".join(
                        str(tag)
                        for tag in tags[:6]
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
            color,

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

    image = get_image(
        entry
    )

    if image:

        embed["thumbnail"] = {
            "url": image
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
            "wait": "true"
        },

        json=payload,

        timeout=20

    )

    response.raise_for_status()


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "========================================"
    )

    print(
        "GGNews Rocket League"
    )

    print(
        "Checking ONLY the last 24 hours"
    )

    print(
        "========================================"
    )

    history = load_history()

    articles = fetch_articles()

    print(
        f"[INFO] Articles from last 24h: "
        f"{len(articles)}"
    )

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

    # الأقدم أولاً، ثم الأحدث
    new_articles.sort(

        key=lambda item:
            get_article_datetime(
                item[0]
            )
            or datetime.min.replace(
                tzinfo=timezone.utc
            )

    )

    new_articles = new_articles[
        -MAX_ARTICLES_PER_RUN:
    ]

    print(
        f"[INFO] New articles to publish: "
        f"{len(new_articles)}"
    )

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
        )

        source = get_source(
            link,
            feed_name
        )

        print(
            f"[AI] Processing: {title}"
        )

        try:

            article = ask_gemini(

                title=title,

                summary=summary,

                source=source,

                link=link

            )

        except Exception as error:

            print(
                f"[AI ERROR] {error}"
            )

            article = fallback_article(
                entry
            )

        try:

            payload = create_discord_payload(

                entry,

                feed_name,

                article

            )

            send_to_discord(
                payload
            )

            history.add(
                key
            )

            published += 1

            print(
                f"[DISCORD] Published: {title}"
            )

            time.sleep(
                1
            )

        except Exception as error:

            print(
                f"[DISCORD ERROR] {error}"
            )

    save_history(
        history
    )

    print(
        "========================================"
    )

    print(
        f"Published: {published}"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":

    main()
