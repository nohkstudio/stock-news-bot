import streamlit as st
import feedparser
import requests
import time
import threading
import json
import os
from datetime import datetime

# --- 설정 파일 관리 ---
CONFIG_FILE = 'config.json'

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {
            "webhook_url": "",
            "keywords": ["삼성전자", "NVDA"],
            "rss_urls": [
                "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",
                "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
            ]
        }
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# --- 봇 로직 ---
sent_links = set()
stop_event = threading.Event()

def run_bot_logic(webhook_url, keywords, rss_urls, status_area):
    status_area.info("🚀 봇 가동 시작! 뉴스를 실시간으로 감시합니다...")
    while not stop_event.is_set():
        for url in rss_urls:
            if stop_event.is_set(): break
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    if entry.link in sent_links: continue
                    for keyword in keywords:
                        if keyword.lower() in entry.title.lower():
                            payload = {"text": f"📢 *[{keyword}] 뉴스 포착!*\n\n*제목:* {entry.title}\n*링크:* {entry.link}"}
                            requests.post(webhook_url, json=payload)
                            sent_links.add(entry.link)
                            break
            except: pass
        for _ in range(60):
            if stop_event.is_set(): break
            time.sleep(1)
    status_area.warning("🛑 봇이 정지되었습니다.")

# --- 화면 구성 ---
st.set_page_config(page_title="주식 뉴스 봇", page_icon="📈")
st.title("📈 나만의 주식 뉴스 봇")
config = load_config()

st.sidebar.header("⚙️ 기본 설정")
new_webhook = st.sidebar.text_input("슬랙 Webhook URL", value=config['webhook_url'], type="password")
if new_webhook != config['webhook_url']:
    config['webhook_url'] = new_webhook
    save_config(config)

col1, col2 = st.columns(2)
with col1:
    st.subheader("🔍 키워드")
    new_kw = st.text_input("키워드 추가", key="kw")
    if new_kw and new_kw not in config['keywords']:
        config['keywords'].append(new_kw)
        save_config(config)
        st.rerun()
    for kw in config['keywords']:
        if st.button(f"삭제 {kw}"):
            config['keywords'].remove(kw)
            save_config(config)
            st.rerun()

with col2:
    st.subheader("🔗 뉴스 소스")
    new_rss = st.text_input("RSS 추가", key="rss")
    if new_rss and new_rss not in config['rss_urls']:
        config['rss_urls'].append(new_rss)
        save_config(config)
        st.rerun()
    for rss in config['rss_urls']:
        if st.button("삭제", key=rss):
            config['rss_urls'].remove(rss)
            save_config(config)
            st.rerun()

st.divider()
status_area = st.empty()
if 'run' not in st.session_state: st.session_state.run = False

if st.button("▶️ 실행", disabled=st.session_state.run):
    st.session_state.run = True
    stop_event.clear()
    threading.Thread(target=run_bot_logic, args=(config['webhook_url'], config['keywords'], config['rss_urls'], status_area)).start()
    st.rerun()

if st.button("⏹ 정지", disabled=not st.session_state.run):
    stop_event.set()
    st.session_state.run = False
    st.rerun()