"""
수집한 Riot API 데이터를 파싱하여 DB에 저장하는 모듈.

담당 역할:
- 매치 JSON → match_participants, timeline_snapshots 파싱
- DB upsert (중복 수집 시 덮어쓰기)
- 원본 JSON 로컬 파일 저장
"""

import json
from pathlib import Path
from datetime import datetime

from loguru import logger

from src.db.init_db import get_connection


# ── 소환사 저장 ───────────────────────────────────────────────

def upsert_summoner(conn, puuid: str, game_name: str, tag_line: str,
                    summoner: dict = None, league: dict = None):
    """소환사 정보 삽입/업데이트."""
    conn.execute("""
        INSERT INTO summoners
            (puuid, game_name, tag_line, summoner_level, profile_icon_id,
             tier, rank, lp, wins, losses, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(puuid) DO UPDATE SET
            game_name       = excluded.game_name,
            tag_line        = excluded.tag_line,
            summoner_level  = excluded.summoner_level,
            profile_icon_id = excluded.profile_icon_id,
            tier            = excluded.tier,
            rank            = excluded.rank,
            lp              = excluded.lp,
            wins            = excluded.wins,
            losses          = excluded.losses,
            updated_at      = CURRENT_TIMESTAMP
    """, (
        puuid,
        game_name,
        tag_line,
        summoner.get("summonerLevel") if summoner else None,
        summoner.get("profileIconId") if summoner else None,
        league.get("tier") if league else None,
        league.get("rank") if league else None,
        league.get("leaguePoints") if league else None,
        league.get("wins") if league else None,
        league.get("losses") if league else None,
    ))


# ── 매치 저장 ─────────────────────────────────────────────────

def save_match(conn, match: dict):
    """매치 기본 정보 + 참가자 성과 저장."""
    info = match.get("info", {})
    match_id = match["metadata"]["matchId"]

    # 1. matches 테이블
    conn.execute("""
        INSERT OR IGNORE INTO matches
            (match_id, game_duration, game_version, queue_id, game_start_ts)
        VALUES (?, ?, ?, ?, ?)
    """, (
        match_id,
        info.get("gameDuration"),
        info.get("gameVersion"),
        info.get("queueId"),
        info.get("gameStartTimestamp"),
    ))

    # 2. 참가자 10명 전원 summoners에 먼저 삽입 (외래 키 제약 충족)
    for p in info.get("participants", []):
        puuid = p.get("puuid")
        if not puuid:
            continue
        conn.execute("""
            INSERT OR IGNORE INTO summoners (puuid, game_name, tag_line)
            VALUES (?, ?, ?)
        """, (
            puuid,
            p.get("riotIdGameName", p.get("summonerName", "")),
            p.get("riotIdTagline", ""),
        ))

    # 3. match_participants 테이블
    for p in info.get("participants", []):
        _save_participant(conn, match_id, p)

def _save_participant(conn, match_id: str, p: dict):
    """참가자 1명 데이터 파싱 후 저장."""
    kills   = p.get("kills", 0)
    deaths  = p.get("deaths", 0)
    assists = p.get("assists", 0)

    # 킬 관여율: (킬 + 어시) / 팀 총 킬 (팀 총 킬은 별도 계산 필요 — 일단 0으로 저장 후 후처리)
    # 분당 CS
    duration_min = p.get("timePlayed", 0) / 60 or 1
    cs_total = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)
    cs_per_min = round(cs_total / duration_min, 2)

    conn.execute("""
        INSERT INTO match_participants
            (match_id, puuid, champion_id, champion_name, position, win,
             kills, deaths, assists, cs_total, cs_per_min, gold_earned,
             vision_score, wards_placed, wards_killed, kp_percent,
             dmg_dealt, dmg_taken)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id, puuid) DO UPDATE SET
            champion_id   = excluded.champion_id,
            champion_name = excluded.champion_name,
            position      = excluded.position,
            win           = excluded.win,
            kills         = excluded.kills,
            deaths        = excluded.deaths,
            assists       = excluded.assists,
            cs_total      = excluded.cs_total,
            cs_per_min    = excluded.cs_per_min,
            gold_earned   = excluded.gold_earned,
            vision_score  = excluded.vision_score,
            wards_placed  = excluded.wards_placed,
            wards_killed  = excluded.wards_killed,
            kp_percent    = excluded.kp_percent,
            dmg_dealt     = excluded.dmg_dealt,
            dmg_taken     = excluded.dmg_taken
    """, (
        match_id,
        p.get("puuid"),
        p.get("championId"),
        p.get("championName"),
        p.get("teamPosition"),       # TOP / JUNGLE / MIDDLE / BOTTOM / UTILITY
        1 if p.get("win") else 0,
        kills,
        deaths,
        assists,
        cs_total,
        cs_per_min,
        p.get("goldEarned"),
        p.get("visionScore"),
        p.get("wardsPlaced"),
        p.get("wardsKilled"),
        0,                           # kp_percent — 후처리에서 업데이트
        p.get("totalDamageDealtToChampions"),
        p.get("totalDamageTaken"),
    ))


# ── 타임라인 저장 ─────────────────────────────────────────────

def save_timeline(conn, match_id: str, timeline: dict):
    """Match Timeline → 분당 스냅샷 파싱 후 저장."""
    frames = timeline.get("info", {}).get("frames", [])

    # 포지션별 상대 라이너 찾기 (participant_id 1~5 vs 6~10)
    for frame in frames:
        minute = frame.get("timestamp", 0) // 60000  # ms → 분
        participant_frames = frame.get("participantFrames", {})

        if not participant_frames:
            continue

        for pid_str, pf in participant_frames.items():
            pid = int(pid_str)
            puuid = _get_puuid_from_timeline(timeline, pid)
            if not puuid:
                continue

            total_gold = pf.get("totalGold", 0)
            cs = (pf.get("minionsKilled", 0) +
                  pf.get("jungleMinionsKilled", 0))
            xp = pf.get("xp", 0)

            # 상대 라이너 찾아서 diff 계산
            opponent_pid = _find_opponent(pid)
            opponent_pf = participant_frames.get(str(opponent_pid), {})
            gold_diff = total_gold - opponent_pf.get("totalGold", 0)
            cs_diff = cs - (
                opponent_pf.get("minionsKilled", 0) +
                opponent_pf.get("jungleMinionsKilled", 0)
            )

            conn.execute("""
                INSERT INTO timeline_snapshots
                    (match_id, puuid, minute, gold, cs, xp, gold_diff, cs_diff)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id, puuid, minute) DO UPDATE SET
                    gold      = excluded.gold,
                    cs        = excluded.cs,
                    xp        = excluded.xp,
                    gold_diff = excluded.gold_diff,
                    cs_diff   = excluded.cs_diff
            """, (match_id, puuid, minute, total_gold, cs, xp, gold_diff, cs_diff))


def _get_puuid_from_timeline(timeline: dict, participant_id: int) -> str:
    """타임라인에서 participant_id → puuid 변환."""
    participants = timeline.get("info", {}).get("participants", [])
    for p in participants:
        if p.get("participantId") == participant_id:
            return p.get("puuid")
    return None


def _find_opponent(participant_id: int) -> int:
    """같은 포지션 상대방 participant_id 반환. (1↔6, 2↔7, 3↔8, 4↔9, 5↔10)"""
    if participant_id <= 5:
        return participant_id + 5
    return participant_id - 5


# ── 킬 관여율 후처리 ──────────────────────────────────────────

def update_kp_percent(conn, match_id: str, match: dict):
    """팀 총 킬 기반으로 kp_percent 업데이트."""
    participants = match.get("info", {}).get("participants", [])

    # 팀별 총 킬 계산 (teamId: 100 = 블루, 200 = 레드)
    team_kills = {100: 0, 200: 0}
    for p in participants:
        team_kills[p.get("teamId", 100)] += p.get("kills", 0)

    for p in participants:
        team_id = p.get("teamId", 100)
        total = team_kills[team_id]
        if total == 0:
            continue
        kp = round((p.get("kills", 0) + p.get("assists", 0)) / total * 100, 1)
        conn.execute("""
            UPDATE match_participants
            SET kp_percent = ?
            WHERE match_id = ? AND puuid = ?
        """, (kp, match_id, p.get("puuid")))


# ── 원본 JSON 저장 ────────────────────────────────────────────

def save_raw_json(data: dict, category: str, name: str):
    """원본 API 응답을 data/raw/{category}/{name}.json으로 저장."""
    path = Path(f"data/raw/{category}/{name}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 통합 저장 함수 ────────────────────────────────────────────

def process_and_save_match(match: dict, timeline: dict = None, save_raw: bool = True):
    """매치 데이터 전체 처리 + 저장 (외부에서 호출하는 메인 함수)."""
    match_id = match["metadata"]["matchId"]
    conn = get_connection()

    try:
        with conn:
            save_match(conn, match)
            update_kp_percent(conn, match_id, match)

            if timeline:
                save_timeline(conn, match_id, timeline)

        if save_raw:
            save_raw_json(match, "matches", match_id)
            if timeline:
                save_raw_json(timeline, "timelines", match_id)

        logger.debug(f"저장 완료: {match_id}")

    except Exception as e:
        logger.error(f"저장 실패 {match_id}: {e}")
        raise
    finally:
        conn.close()
