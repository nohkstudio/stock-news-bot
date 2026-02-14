import streamlit as st
import requests
import json
import base64

st.title("🛠 뉴스봇 설정 관리")

# GitHub 정보
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]
BRANCH = st.secrets["GITHUB_BRANCH"]
FILE_PATH = "config.json"

# 현재 config.json 불러오기
@st.cache_data
def load_config():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content), data["sha"]

config, sha = load_config()

keywords = st.text_area("키워드 (한 줄에 하나)", "\n".join(config["keywords"]))
rss_feeds = st.text_area("RSS 주소 (한 줄에 하나)", "\n".join(config["rss_feeds"]))

quiet_start = st.text_input("알림 제외 시작시간 (HH:MM)", config["quiet_hours"]["start"])
quiet_end = st.text_input("알림 제외 종료시간 (HH:MM)", config["quiet_hours"]["end"])

if st.button("💾 저장"):
    new_config = {
        "keywords": [k.strip() for k in keywords.split("\n") if k.strip()],
        "rss_feeds": [r.strip() for r in rss_feeds.split("\n") if r.strip()],
        "quiet_hours": {
            "start": quiet_start,
            "end": quiet_end
        }
    }

    content_encoded = base64.b64encode(json.dumps(new_config, indent=2).encode()).decode()

    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {
        "message": "Update config via Streamlit UI",
        "content": content_encoded,
        "sha": sha,
        "branch": BRANCH
    }

    res = requests.put(url, headers=headers, json=payload)

    if res.status_code == 200:
        st.success("✅ 저장 완료! GitHub에 반영되었습니다.")
    else:
        st.error("❌ 저장 실패")
