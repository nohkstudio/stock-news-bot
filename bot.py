import json
import os
import time
import hashlib
import feedparser
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

CONFIG_PATH = "config.json"
STATE_PATH = "state.json"  # 중복 전송 방지용(최근 전송 기록)

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_state():
    if not os.path.exists(STATE_PATH):
        return {"sent": {}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def now_kst():
    return datetime.now(KST)

def parse_hhmm(s: str):
    # "23:30" -> (23, 30)
    hh, mm = s.strip().split(":")
    return int(hh), int(mm)

def in_quiet_hours(now: datetime, quiet_ranges):
    # quiet_ranges: [{"start":"23:30","end":"07:30"}, ...]
    # 자정 넘기는 구간도 처리
    if not quiet_ranges:
        return False

    cur_min = now.hour * 60 + now.minute

    for r in quiet_ranges:
        sh, sm = parse_hhmm(r["start"])
        eh, em = parse_hhmm(r["end"])
        start_min = sh * 60 + sm
        end_min = eh * 60 + em

        if start_min <= end_min:
            # 같은 날 안에서 끝남 (예: 13:00~15:00)
            if start_min <= cur_min < end_min:
                return True
        else:
            # 자정 넘김 (예: 23:30~07:30)
            if cur_min >= start_min or cur_min < end_min:
                return True

    return False

def normalize_text(s: str) -> str:
    return (s or "").lower()

def contains_keyword(title: str, summary: str, keywords):
    t = normalize_text(title)
    s = normalize_text(summary)
    for kw in keywords:
        k = normalize_text(kw)
        if k and (k in t or k in s):
            return True
    return False

def make_key(link: str) -> str:
    # 링크 기반 중복키 (혹시 링크가 길면 해시)
    return hashlib.sha256(link.encode("utf-8")).hexdigest()

def post_to_slack(webhook_url: str, text: str):
    # Slack Incoming Webhook
    resp = requests.post(
        webhook_url,
        json={"text": text},
        timeout=15
    )
    # 실패하면 예외로 로그 확인 가능하게
    resp.raise_for_status()

def main():
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("SLACK_WEBHOOK_URL 환경변수가 없습니다. GitHub Secrets에 설정하세요.")

    config = load_config()
    keywords = config.get("keywords", [])
    rss_feeds = config.get("rss_feeds", [])
    quiet_ranges = config.get("quiet_hours_kr", [])

    now = now_kst()
    if in_quiet_hours(now, quiet_ranges):
        print(f"[KST {now.strftime('%Y-%m-%d %H:%M')}] Quiet hours - skipping Slack send.")
        return

    # 중복 전송 방지: state.json에 최근 전송 기록 저장
    # (주의) GitHub Actions는 매 실행이 깨끗한 환경이라 state가 유지되지 않을 수 있음.
    # 그래도 RSS가 최신 위주라 실무에선 대개 충분하며,
    # 더 강한 영속이 필요하면 다음 단계로 Cache/Redis 등을 붙이면 됨.
    state = load_state()
    sent = state.get("sent", {})
    cutoff_seconds = 60 * 60 * 24  # 24시간 내 중복 방지

    now_ts = int(time.time())

    # 오래된 기록 정리
    for k in list(sent.keys()):
        if now_ts - int(sent[k]) > cutoff_seconds:
            del sent[k]

    total_found = 0
    total_sent = 0

    headers = {
        "User-Agent": "news-bot/1.0 (+github actions)"
    }

    for url in rss_feeds:
        try:
            feed = feedparser.parse(url, request_headers=headers)
        except Exception as e:
            print(f"[WARN] feed parse error: {url} -> {e}")
            continue

        entries = getattr(feed, "entries", []) or []
        for entry in entries:
            link = getattr(entry, "link", "") or ""
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""

            if not link:
                continue

            if contains_keyword(title, summary, keywords):
                total_found += 1
                key = make_key(link)
                if key in sent:
                    continue

                text = f"📢 *[뉴스 포착]*\n*제목*: {title}\n*링크*: {link}"
                try:
                    post_to_slack(webhook_url, text)
                    sent[key] = now_ts
                    total_sent += 1
                except Exception as e:
                    print(f"[WARN] slack send failed: {e}")

    state["sent"] = sent
    save_state(state)

    print(f"Done. matched={total_found}, sent={total_sent}")

if __name__ == "__main__":
    main()