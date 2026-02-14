import streamlit as st
import json
import base64
import requests

st.set_page_config(page_title="News Bot Settings", layout="centered")
st.title("🛠 뉴스봇 설정 관리")

# ===== GitHub 정보 (Secrets에서 읽음) =====
if "GITHUB_TOKEN" not in st.secrets:
    st.error("Streamlit Secrets에 GITHUB_TOKEN을 설정하세요.")
    st.stop()

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
CONFIG_PATH = "config.json"


def github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }


def load_config():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONFIG_PATH}"
    r = requests.get(url, headers=github_headers(), params={"ref": GITHUB_BRANCH})
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content), data["sha"]


def save_config(new_config, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONFIG_PATH}"
    encoded = base64.b64encode(
        json.dumps(new_config, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": "Update config via Streamlit",
        "content": encoded,
        "branch": GITHUB_BRANCH,
        "sha": sha
    }

    r = requests.put(url, headers=github_headers(), json=payload)
    r.raise_for_status()


# ===== 현재 config 불러오기 =====
config, sha = load_config()

keywords = config.get("keywords", [])
rss_feeds = config.get("rss_feeds", [])
quiet_hours = config.get("quiet_hours_kr", [])

# ===== UI =====
st.subheader("🔍 키워드")
kw_text = st.text_area(
    "줄바꿈으로 입력",
    value="\n".join(keywords),
    height=150
)

st.subheader("🔗 RSS 주소")
rss_text = st.text_area(
    "줄바꿈으로 입력",
    value="\n".join(rss_feeds),
    height=150
)

st.subheader("🌙 알림 제외 시간 (한국시간)")
qh_text = st.text_area(
    "예: 23:30~07:30 (여러 줄 가능)",
    value="\n".join(
        [f'{x["start"]}~{x["end"]}' for x in quiet_hours]
    ),
    height=100
)

def parse_quiet(text):
    result = []
    for line in text.splitlines():
        if "~" in line:
            start, end = line.strip().split("~")
            result.append({"start": start.strip(), "end": end.strip()})
    return result


if st.button("💾 저장"):
    new_config = {
        "keywords": [x.strip() for x in kw_text.splitlines() if x.strip()],
        "rss_feeds": [x.strip() for x in rss_text.splitlines() if x.strip()],
        "quiet_hours_kr": parse_quiet(qh_text)
    }

    save_config(new_config, sha)
    st.success("저장 완료! 다음 실행부터 반영됩니다.")
