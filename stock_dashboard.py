import streamlit as st
import requests
import json
import base64

st.set_page_config(page_title="뉴스봇 설정", layout="centered")
st.title("🛠 뉴스봇 설정 관리")

# ===== Secrets =====
# Streamlit Secrets에 아래 키가 있어야 함:
# GITHUB_TOKEN, GITHUB_REPO
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]
BRANCH = st.secrets.get("GITHUB_BRANCH", "main")

FILE_PATH = "config.json"

def gh_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

@st.cache_data
def load_config():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    r = requests.get(url, headers=gh_headers(), params={"ref": BRANCH}, timeout=20)
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content), data["sha"]

def save_config(new_config, sha):
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    encoded = base64.b64encode(
        json.dumps(new_config, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": "Update config via Streamlit UI",
        "content": encoded,
        "sha": sha,
        "branch": BRANCH,
    }
    r = requests.put(url, headers=gh_headers(), json=payload, timeout=20)
    r.raise_for_status()

config, sha = load_config()

# ===== UI: keywords / rss =====
keywords_text = st.text_area(
    "키워드 (한 줄에 하나)",
    "\n".join(config.get("keywords", [])),
    height=140,
)

rss_text = st.text_area(
    "RSS 주소 (한 줄에 하나)",
    "\n".join(config.get("rss_feeds", [])),
    height=140,
)

# ===== UI: quiet hours (KST) =====
st.subheader("🌙 알림 제외 시간 (한국시간)")
st.caption("형식: 23:30~07:30  (여러 줄 가능, 자정 넘어가는 구간 OK)")

qh = config.get("quiet_hours_kr", [])
qh_lines = [f'{x.get("start","")}~{x.get("end","")}' for x in qh]
quiet_text = st.text_area("알림 제외 시간", "\n".join([l for l in qh_lines if l.strip()]), height=110)

def parse_quiet(text: str):
    ranges = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or "~" not in line:
            continue
        a, b = [x.strip() for x in line.split("~", 1)]
        if len(a) == 5 and len(b) == 5 and ":" in a and ":" in b:
            ranges.append({"start": a, "end": b})
    return ranges

if st.button("💾 저장"):
    new_config = dict(config)  # 기존 키들(예: interval_minutes 등) 유지
    new_config["keywords"] = [x.strip() for x in keywords_text.splitlines() if x.strip()]
    new_config["rss_feeds"] = [x.strip() for x in rss_text.splitlines() if x.strip()]
    new_config["quiet_hours_kr"] = parse_quiet(quiet_text)

    try:
        save_config(new_config, sha)
        st.success("✅ 저장 완료! GitHub config.json에 반영되었습니다.")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"❌ 저장 실패: {e}")
