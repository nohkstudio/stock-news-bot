import streamlit as st
import threading
import time
import feedparser
import requests
from datetime import datetime
# 에러 해결을 위한 핵심 라이브러리 추가
from streamlit.runtime.scriptrunner import add_script_run_ctx

# --- 설정 및 초기화 ---
if 'keywords' not in st.session_state:
    st.session_state.keywords = ['삼성전자', 'NVDA', 'sk하이닉스', 'skhynix']
if 'rss_feeds' not in st.session_state:
    st.session_state.rss_feeds = [
        'https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko',
        'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en'
    ]
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'last_links' not in st.session_state:
    st.session_state.last_links = set()

# --- 뉴스 감시 로직 ---
def run_bot_logic(keywords, rss_feeds, webhook_url):
    status_area = st.empty()
    status_area.info("🚀 봇 가동 시작! 뉴스를 실시간으로 감시합니다...")
    
    while st.session_state.is_running:
        for url in rss_feeds:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if entry.link not in st.session_state.last_links:
                    # 제목이나 요약에 키워드가 있는지 확인
                    if any(kw.lower() in entry.title.lower() for kw in keywords):
                        msg = {
                            "text": f"📢 *[뉴스 포착]*\n*제목*: {entry.title}\n*링크*: {entry.link}"
                        }
                        try:
                            requests.post(webhook_url, json=msg)
                            st.session_state.last_links.add(entry.link)
                        except Exception as e:
                            print(f"전송 실패: {e}")
        
        # 10분마다 확인 (너무 자주하면 차단될 수 있음)
        time.sleep(600)

# --- UI 레이아웃 ---
st.title("📈 나만의 주식 뉴스 봇")

with st.sidebar:
    st.header("⚙️ 기본 설정")
    webhook_url = st.text_input("슬랙 Webhook URL", type="password", help="슬랙 API에서 생성한 URL을 입력하세요.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🔍 키워드")
    new_kw = st.text_input("키워드 추가", key="new_kw_input")
    if st.button("추가") and new_kw:
        st.session_state.keywords.append(new_kw)
    
    for kw in st.session_state.keywords:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(kw)
        if c2.button("삭제", key=f"del_{kw}"):
            st.session_state.keywords.remove(kw)
            st.rerun()

with col2:
    st.subheader("🔗 뉴스 소스")
    new_rss = st.text_input("RSS 추가", key="new_rss_input")
    if st.button("추가", key="rss_add_btn") and new_rss:
        st.session_state.rss_feeds.append(new_rss)
    
    for rss in st.session_state.rss_feeds:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(rss[:30] + "...")
        if c2.button("삭제", key=f"del_{rss}"):
            st.session_state.rss_feeds.remove(rss)
            st.rerun()

st.divider()

# --- 실행 버튼 제어 ---
if not st.session_state.is_running:
    if st.button("▶️ 실행"):
        if not webhook_url:
            st.error("슬랙 Webhook URL을 먼저 입력해 주세요!")
        else:
            st.session_state.is_running = True
            # 쓰레드 생성 및 컨텍스트 연결 (에러 해결 핵심)
            thread = threading.Thread(
                target=run_bot_logic, 
                args=(st.session_state.keywords, st.session_state.rss_feeds, webhook_url)
            )
            add_script_run_ctx(thread) 
            thread.start()
            st.rerun()
else:
    st.success("봇이 현재 가동 중입니다.")
    if st.button("⏹ 정지"):
        st.session_state.is_running = False
        st.rerun()