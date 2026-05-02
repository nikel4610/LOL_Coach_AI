"""
LoL Coach AI — Streamlit MVP

실행:
    streamlit run app.py
"""

import sqlite3
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from src.analysis.compare import build_coach_payload
from src.coach.feedback import get_coach_feedback

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/lol_coach.db")

TIER_ORDER = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM",
              "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]

TIER_COLOR = {
    "IRON": "#8B8B8B", "BRONZE": "#CD7F32", "SILVER": "#A8A9AD",
    "GOLD": "#FFD700", "PLATINUM": "#00C4B4", "EMERALD": "#00A86B",
    "DIAMOND": "#B9F2FF", "MASTER": "#9D48E0", "GRANDMASTER": "#FF4444",
    "CHALLENGER": "#F4C874",
}

POSITION_KR = {
    "TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드",
    "BOTTOM": "원딜", "UTILITY": "서폿",
}


@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def search_summoner(conn, name: str, tag: str | None):
    if tag:
        row = conn.execute(
            "SELECT puuid, game_name, tag_line, tier, rank, lp FROM summoners "
            "WHERE game_name = ? AND tag_line = ?",
            (name, tag),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT puuid, game_name, tag_line, tier, rank, lp FROM summoners "
            "WHERE game_name = ? AND tier IS NOT NULL ORDER BY lp DESC LIMIT 1",
            (name,),
        ).fetchone()
    return row


def render_comparison_table(comparison: list[dict]):
    st.markdown("#### 지표 비교")

    primary   = [r for r in comparison if r["is_primary"]]
    secondary = [r for r in comparison if not r["is_primary"]]

    def render_rows(rows):
        for r in rows:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            arrow  = "▲" if r["above_avg"] else "▼"
            color  = "green" if r["above_avg"] else "red"
            pct    = f"{r['diff_pct']:+.1f}%" if r["diff_pct"] is not None else f"{r['diff']:+.1f}"
            unit   = r["unit"]

            col1.markdown(r["label"])
            col2.markdown(f"**{r['personal']}{unit}**")
            col3.markdown(f"{r['tier_avg']}{unit}")
            col4.markdown(f":{color}[{arrow} {pct}]")

    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    col1.markdown("**지표**")
    col2.markdown("**내 기록**")
    col3.markdown("**티어 평균**")
    col4.markdown("**차이**")
    st.divider()

    if primary:
        st.markdown("**핵심 지표**")
        render_rows(primary)

    if secondary:
        with st.expander("참고 지표 보기"):
            render_rows(secondary)


def render_phase_section(payload: dict):
    phase     = payload["analysis"].get("phase", {})
    gold_curve = payload["analysis"].get("gold_curve", [])

    if not phase:
        return

    st.markdown("#### 라인전 단계별 성장")

    # 체크포인트 스냅샷 테이블
    checkpoint_data = []
    for m in [5, 10, 14, 20]:
        cs = phase.get(f"cs_at_{m}")
        gd = phase.get(f"gold_diff_{m}")
        cd = phase.get(f"cs_diff_{m}")
        if cs is None:
            continue
        phase_label = "초반" if m <= 14 else "중반"
        checkpoint_data.append({
            "단계": phase_label,
            "시간": f"{m}분",
            "CS": cs,
            "골드차": f"{gd:+.0f}" if gd is not None else "-",
            "CS차": f"{cd:+.1f}" if cd is not None else "-",
        })

    if checkpoint_data:
        df = pd.DataFrame(checkpoint_data).set_index("시간")
        st.dataframe(df, use_container_width=True)

    # 분당 골드차 추이 라인 차트
    if gold_curve:
        df_curve = pd.DataFrame(gold_curve).set_index("minute")[["avg_gold_diff"]]
        df_curve.index.name = "분"
        df_curve.columns = ["골드차"]
        st.markdown("**분당 골드차 추이**")
        st.line_chart(df_curve)


def render_summoner_card(payload: dict):
    s      = payload["summoner"]
    tier   = s["tier"]
    color  = TIER_COLOR.get(tier, "#FFFFFF")
    pos_kr = POSITION_KR.get(payload["main_position"], payload["main_position"])

    st.markdown(
        f"""
        <div style="
            border: 2px solid {color};
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 16px;
        ">
            <h3 style="margin:0; color:{color};">
                {s['game_name']}<span style="color:#888; font-size:0.8em;">#{s['tag_line']}</span>
            </h3>
            <p style="margin:4px 0 0 0; color:#ccc;">
                {tier} {s['rank']} &nbsp;·&nbsp; {s['lp']} LP &nbsp;·&nbsp;
                주 포지션: <b>{pos_kr}</b> &nbsp;·&nbsp;
                분석 게임: <b>{payload['games_analyzed']}게임</b>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if payload.get("warnings"):
        for w in payload["warnings"]:
            st.warning(w)
    if payload.get("low_sample"):
        st.warning("분석 게임 수가 적어 신뢰도가 낮을 수 있습니다.")


# ── 페이지 설정 ───────────────────────────────���───────────────

st.set_page_config(page_title="LoL Coach AI", page_icon="⚔️", layout="centered")
st.title("LoL Coach AI")
st.caption("소환사 전적을 분석하고 AI 코치 피드백을 받아보세요.")

# ── 검색 UI ──────────────────────────────────────────────────

with st.form("search_form"):
    raw = st.text_input(
        "소환사명 입력",
        placeholder="닉네임#KR1  (태그 생략 시 자동 검색)",
    )
    submitted = st.form_submit_button("분석하기", use_container_width=True)

if not submitted or not raw.strip():
    st.stop()

# ── 소환사 조회 ───────────────────────────────────────────────

parts = raw.strip().split("#", 1)
name  = parts[0].strip()
tag   = parts[1].strip() if len(parts) > 1 else None

conn = get_conn()
row  = search_summoner(conn, name, tag)

if not row:
    hint = f"'{name}#{tag}'" if tag else f"'{name}'"
    st.error(f"{hint} 소환사를 DB에서 찾을 수 없습니다. 수집된 소환사만 분석 가능합니다.")
    st.stop()

puuid = row["puuid"]
tier  = row["tier"]

# ── 분석 payload 생성 ─────────────────────────────────────────

with st.spinner("데이터 분석 중..."):
    try:
        payload = build_coach_payload(conn, puuid, tier=tier)
    except Exception as e:
        st.error(f"분석 중 오류가 발생했습니다: {e}")
        st.stop()

# ── 결과 표시 ─────────────────────────────────────────────────

render_summoner_card(payload)

tab1, tab2 = st.tabs(["📊 지표 비교", "🤖 AI 코치 피드백"])

with tab1:
    render_comparison_table(payload["comparison"])
    st.divider()
    render_phase_section(payload)

with tab2:
    with st.spinner("AI 코치 피드백 생성 중..."):
        try:
            feedback = get_coach_feedback(payload)
        except Exception as e:
            st.error(f"피드백 생성 중 오류가 발생했습니다: {e}")
            st.stop()
    st.markdown(feedback.replace("~", r"\~"))
