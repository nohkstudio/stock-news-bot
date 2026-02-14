import os
import json
import feedparser
import requests
from datetime import datetime, timedelta, timezone

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# ============================
# 설정 불러오기
# ============================

with open("config_realtime.json", "r", encoding="utf-8") as f:
    config = json.load(f)

KEYWORDS = config.get("keywords", [])
RSS_FEEDS = config.get("rss_feeds", [])

# 감정 태그용 키워드
POSITIVE_WORDS = ["수주", "증가", "확대", "성장", "상승", "개선", "흑자", "인상"]
NEGATIVE_WORDS = ["감소", "하락", "적자", "축소", "우려", "재고 증가", "감산"]

# ============================
# 유틸 함수
# ============================

def slack_post(message):
    if not SLACK_WEBHOOK_URL:
        print("❌ SLACK_WEBHOOK_URL 없음")
        return
    
    requests.post(SLACK_WEBHOOK_URL, json={"text": message})


def tag_sentiment(text):
    for w in POSITIVE_WORDS:
        if w in text:
            return "📈 긍정"
    for w in NEGATIVE_WORDS:
        if w in text:
            return "📉 부정"
    return "➖ 중립"


def match_keywords(text):
    matched = []
    for kw in KEYWORDS:
        if kw.lower() in text.lower():
            matched.append(kw)
    return matched


# ============================
# 메인 로직
# ============================

def main():
    now_utc = datetime.now(timezone.utc)
    one_hour_ago = now_utc - timedelta(hours=1)

    sent_count = 0

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")

            text = f"{title} {summary}"

            # 발행 시간 체크
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if pub_dt < one_hour_ago:
                    continue
            else:
                continue

            matched = match_keywords(text)
            if not matched:
                continue

            sentiment = tag_sentiment(text)

            msg = (
                f"{sentiment}\n"
                f"🎯 키워드: {', '.join(matched)}\n"
                f"📰 {title}\n"
                f"{link}"
            )

            slack_post(msg)
            sent_count += 1

    print(f"Sent: {sent_count}")


if __name__ == "__main__":
    main()
