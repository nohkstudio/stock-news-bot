import os
import re
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtparser

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

# config.json 그대로 활용 (Streamlit UI에서 저장한 값)
import json
CONFIG_PATH = "config.json"

POSITIVE = ["가격 상승", "수요 증가", "증가", "반등", "회복", "상승", "호조", "강세", "확대"]
NEGATIVE = ["재고 증가", "가격 하락", "감소", "둔화", "감산", "부진", "경고", "하향", "약세", "축소"]

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def within_last_24h(published_dt_utc: datetime) -> bool:
    now_utc = datetime.now(timezone.utc)
    return published_dt_utc >= now_utc - timedelta(hours=24)

def tag_sentiment(text: str) -> str:
    t = text.lower()
    pos = sum(1 for w in POSITIVE if w.lower() in t)
    neg = sum(1 for w in NEGATIVE if w.lower() in t)
    if pos > neg and pos > 0:
        return "📈 긍정"
    if neg > pos and neg > 0:
        return "📉 부정"
    return "⚪ 중립"

def slack_post(text: str):
    r = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=15)
    r.raise_for_status()

def main():
    cfg = load_config()
    keywords = [k.strip() for k in cfg.get("keywords", []) if k.strip()]
    rss_feeds = [u.strip() for u in cfg.get("rss_feeds", []) if u.strip()]

    items = []
    for url in rss_feeds:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = getattr(e, "title", "")
            link = getattr(e, "link", "")
            summary = getattr(e, "summary", "")
            published = getattr(e, "published", None) or getattr(e, "updated", None)
            if not published:
                continue
            try:
                pub_dt = dtparser.parse(published)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                pub_dt_utc = pub_dt.astimezone(timezone.utc)
            except Exception:
                continue

            if not within_last_24h(pub_dt_utc):
                continue

            text = f"{title}\n{summary}"
            matched = [k for k in keywords if re.search(re.escape(k), text, re.IGNORECASE)]
            if not matched:
                continue

            sentiment = tag_sentiment(text)
            items.append({
                "published": pub_dt_utc,
                "title": title,
                "link": link,
                "matched": matched,
                "sentiment": sentiment
            })

    items.sort(key=lambda x: x["published"], reverse=True)

    total = len(items)
    pos = sum(1 for i in items if i["sentiment"].startswith("📈"))
    neg = sum(1 for i in items if i["sentiment"].startswith("📉"))
    neu = total - pos - neg

    # 상위 10개만 링크로
    top = items[:10]
    lines = []
    for i in top:
        mk = ", ".join(i["matched"][:3])
        lines.append(f"- {i['sentiment']} [{mk}] {i['title']}\n  {i['link']}")

    report_date_kst = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")
    msg = (
        f"🗞️ *일간 리포트* ({report_date_kst}, 최근 24시간)\n"
        f"총 {total}건 | 📈 {pos} | 📉 {neg} | ⚪ {neu}\n\n"
        f"*Top 기사*\n" + ("\n".join(lines) if lines else "- (해당 키워드 기사 없음)")
    )

    slack_post(msg)

if __name__ == "__main__":
    main()
