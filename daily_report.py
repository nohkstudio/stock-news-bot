import os
import json
import requests
import feedparser
from datetime import datetime, timedelta, timezone

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# =============================
# 설정 불러오기
# =============================
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

KEYWORDS = config.get("keywords", [])
RSS_FEEDS = config.get("rss_feeds", [])

# =============================
# 감정 태깅
# =============================
POSITIVE_WORDS = ["수주", "증가", "확대", "성장", "상승", "개선", "호조", "흑자"]
NEGATIVE_WORDS = ["감소", "하락", "적자", "축소", "우려", "재고 증가", "둔화", "리스크"]

def tag_sentiment(text):
    for word in NEGATIVE_WORDS:
        if word in text:
            return "📉 부정"
    for word in POSITIVE_WORDS:
        if word in text:
            return "📈 긍정"
    return "⚪ 중립"

# =============================
# 슬랙 전송
# =============================
def slack_post(message):
    if not SLACK_WEBHOOK_URL:
        print("No Slack Webhook URL")
        return
    
    payload = {"text": message}
    requests.post(SLACK_WEBHOOK_URL, json=payload)

# =============================
# 메인 실행
# =============================
def main():
    all_articles = []
    matched_articles = []
    sent_count = 0

    now_utc = datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(hours=24)

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            title = entry.title
            link = entry.link

            if not hasattr(entry, "published_parsed"):
                continue

            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            if pub_dt < yesterday_utc:
                continue

            all_articles.append(title)

            matched = [kw for kw in KEYWORDS if kw.lower() in title.lower()]
            if not matched:
                continue

            sentiment = tag_sentiment(title)

            matched_articles.append({
                "published": pub_dt,
                "title": title,
                "link": link,
                "matched": matched,
                "sentiment": sentiment
            })

    matched_articles.sort(key=lambda x: x["published"], reverse=True)

    total = len(matched_articles)
    pos = sum(1 for i in matched_articles if i["sentiment"].startswith("📈"))
    neg = sum(1 for i in matched_articles if i["sentiment"].startswith("📉"))
    neu = total - pos - neg

    top = matched_articles[:10]

    lines = []
    for item in top:
        mk = ", ".join(item["matched"][:3])
        lines.append(f"{item['sentiment']} [{mk}] {item['title']}\n{item['link']}")

    report_date_kst = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")

    msg = (
        f"📊 *일간 반도체 리포트* ({report_date_kst}, 최근 24시간)\n\n"
        f"총 {total}건  |  📈 {pos}  📉 {neg}  ⚪ {neu}\n\n"
        f"*Top 기사*\n"
        + ("\n\n".join(lines) if lines else "❌ 해당 키워드 기사 없음")
    )

    slack_post(msg)
    sent_count = 1

    # 🔍 디버그 로그
    print(f"Collected: {len(all_articles)}")
    print(f"Matched: {len(matched_articles)}")
    print(f"Sent: {sent_count}")

# =============================
if __name__ == "__main__":
    main()
