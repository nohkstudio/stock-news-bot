import os
import json
import time
import requests
import feedparser
from datetime import datetime, timedelta, timezone

# =========================
# ENV
# =========================
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# daily report는 기본적으로 "리포트 전용" 설정을 보도록!
# 필요하면 GitHub Actions workflow에서 CONFIG_PATH를 바꿔 끼울 수 있음
CONFIG_PATH = os.getenv("CONFIG_PATH", "config_report.json")

# 지난 몇 시간치 기사로 리포트 만들지 (기본 24시간)
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "24"))

# =========================
# LOAD CONFIG
# =========================
def load_config(path: str) -> dict:
    # 혹시 파일이 없으면 기존 config.json로 fallback (초기 마이그레이션 편의)
    if not os.path.exists(path) and os.path.exists("config.json"):
        path = "config.json"

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config(CONFIG_PATH)

KEYWORDS = config.get("keywords", [])
RSS_FEEDS = config.get("rss_feeds", [])

# 감정 태깅 (간단 버전)
POSITIVE_WORDS = ["수주", "증가", "확대", "성장", "상승", "개선", "호조", "흑자", "인상", "상향", "강세", "회복"]
NEGATIVE_WORDS = ["감소", "하락", "적자", "축소", "우려", "재고 증가", "둔화", "리스크", "부진", "압박", "약세", "경고"]


# =========================
# HELPERS
# =========================
def safe_text(s):
    if not s:
        return ""
    return str(s)

def entry_datetime_utc(entry) -> datetime:
    """
    RSS entry에서 시간을 최대한 안전하게 UTC datetime으로 뽑음
    """
    # feedparser는 published_parsed / updated_parsed 등을 time.struct_time로 줌
    t = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        t = entry.published_parsed
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        t = entry.updated_parsed

    if t:
        return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)

    # 시간이 없으면 "지금"으로 처리
    return datetime.now(timezone.utc)

def match_keywords(text: str, keywords: list[str]) -> list[str]:
    text_l = text.lower()
    matched = []
    for k in keywords:
        k = safe_text(k).strip()
        if not k:
            continue
        if k.lower() in text_l:
            matched.append(k)
    return matched

def tag_sentiment(text: str) -> str:
    t = text.lower()
    pos = any(w.lower() in t for w in POSITIVE_WORDS)
    neg = any(w.lower() in t for w in NEGATIVE_WORDS)

    # 우선순위: 둘 다 있으면 중립
    if pos and not neg:
        return "📈 긍정"
    if neg and not pos:
        return "📉 부정"
    return "⚪ 중립"

def slack_post(text: str):
    if not SLACK_WEBHOOK_URL:
        print("ERROR: SLACK_WEBHOOK_URL is not set")
        return False

    payload = {"text": text}
    r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=20)
    if r.status_code >= 300:
        print("Slack error:", r.status_code, r.text[:300])
        return False
    return True


# =========================
# MAIN
# =========================
def main():
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=LOOKBACK_HOURS)

    items = []
    seen_links = set()

    total_collected = 0
    total_matched = 0

    for feed_url in RSS_FEEDS:
        feed_url = safe_text(feed_url).strip()
        if not feed_url:
            continue

        d = feedparser.parse(feed_url)
        for e in d.entries:
            total_collected += 1

            title = safe_text(getattr(e, "title", ""))
            summary = safe_text(getattr(e, "summary", ""))
            link = safe_text(getattr(e, "link", ""))

            # 중복 링크 제거
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)

            pub_dt = entry_datetime_utc(e)
            if pub_dt < cutoff:
                continue

            text = f"{title}\n{summary}"
            matched = match_keywords(text, KEYWORDS)

            # 키워드가 하나도 없으면 리포트에 안 넣음
            if not matched:
                continue

            total_matched += 1
            sentiment = tag_sentiment(text)

            items.append({
                "published": pub_dt,
                "title": title,
                "link": link,
                "matched": matched,
                "sentiment": sentiment,
            })

    # 최신순
    items.sort(key=lambda x: x["published"], reverse=True)

    # 통계
    total = len(items)
    pos = sum(1 for i in items if i["sentiment"].startswith("📈"))
    neg = sum(1 for i in items if i["sentiment"].startswith("📉"))
    neu = total - pos - neg

    # 상위 N개만
    TOP_N = int(os.getenv("TOP_N", "20"))
    top = items[:TOP_N]

    lines = []
    for i in top:
        mk = ", ".join(i["matched"][:5])
        lines.append(f"- {i['sentiment']} [{mk}] {i['title']}\n  {i['link']}")

    report_date_kst = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")
    header = (
        f"📊 *일간 리포트* ({report_date_kst}, 최근 {LOOKBACK_HOURS}시간)\n"
        f"총 {total}건 | 📈 {pos} | 📉 {neg} | ⚪ {neu}\n"
    )
    body = "*Top 기사*\n" + ("\n".join(lines) if lines else "- (해당 키워드 기사 없음)")

    ok = slack_post(header + "\n" + body)

    # 로그 (Actions에서 확인)
    print(f"Collected: {total_collected}")
    print(f"Matched: {total_matched}")
    print(f"Sent: {1 if ok else 0}")


if __name__ == "__main__":
    main()
