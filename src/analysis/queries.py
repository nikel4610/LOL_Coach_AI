# src/analysis/queries.py
"""
개인 퍼포먼스 집계 쿼리 모음.
모든 함수는 sqlite3.Connection을 받아 dict 또는 list[dict]를 반환합니다.
"""

import sqlite3
from typing import Optional


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    """sqlite3 Row → dict 변환 헬퍼"""
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ──────────────────────────────────────────────
# 1. 기본 전적 요약 (승률 / KDA / 챔피언별)
# ──────────────────────────────────────────────

def get_overall_stats(conn: sqlite3.Connection, puuid: str) -> dict:
    """소환사 전체 평균 지표 반환"""
    sql = """
        SELECT
            COUNT(*)                                    AS games,
            ROUND(AVG(win) * 100, 1)                    AS win_rate,
            ROUND(AVG(kills), 2)                        AS avg_kills,
            ROUND(AVG(deaths), 2)                       AS avg_deaths,
            ROUND(AVG(assists), 2)                      AS avg_assists,
            ROUND(
                (AVG(kills) + AVG(assists))
                / MAX(AVG(deaths), 1.0), 2
            )                                           AS kda,
            ROUND(AVG(cs_per_min), 2)                   AS avg_cs_per_min,
            ROUND(AVG(vision_score), 1)                 AS avg_vision_score,
            ROUND(AVG(kp_percent), 1)                   AS avg_kp_percent,
            ROUND(AVG(dmg_dealt), 0)                    AS avg_dmg_dealt
        FROM match_participants
        WHERE puuid = ?
    """
    cur = conn.execute(sql, (puuid,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else {}


def get_champion_stats(
    conn: sqlite3.Connection,
    puuid: str,
    min_games: int = 2
) -> list[dict]:
    """챔피언별 전적 요약 (min_games 이상 플레이한 챔피언만)"""
    sql = """
        SELECT
            champion_name,
            COUNT(*)                                    AS games,
            ROUND(AVG(win) * 100, 1)                    AS win_rate,
            ROUND(
                (AVG(kills) + AVG(assists))
                / MAX(AVG(deaths), 1.0), 2
            )                                           AS kda,
            ROUND(AVG(cs_per_min), 2)                   AS avg_cs_per_min,
            ROUND(AVG(kp_percent), 1)                   AS avg_kp_percent
        FROM match_participants
        WHERE puuid = ?
        GROUP BY champion_name
        HAVING COUNT(*) >= ?
        ORDER BY games DESC, win_rate DESC
    """
    cur = conn.execute(sql, (puuid, min_games))
    return _rows_to_dicts(cur)


def get_position_stats(conn: sqlite3.Connection, puuid: str) -> list[dict]:
    """포지션별 전적 요약"""
    sql = """
        SELECT
            position,
            COUNT(*)                                    AS games,
            ROUND(AVG(win) * 100, 1)                    AS win_rate,
            ROUND(AVG(cs_per_min), 2)                   AS avg_cs_per_min,
            ROUND(AVG(vision_score), 1)                 AS avg_vision_score,
            ROUND(AVG(kp_percent), 1)                   AS avg_kp_percent,
            ROUND(AVG(dmg_dealt), 0)                    AS avg_dmg_dealt
        FROM match_participants
        WHERE puuid = ?
        GROUP BY position
        ORDER BY games DESC
    """
    cur = conn.execute(sql, (puuid,))
    return _rows_to_dicts(cur)


# ──────────────────────────────────────────────
# 2. 라인전 지표 (10분 골드차 / CS차)
# ──────────────────────────────────────────────

def get_laning_stats(conn: sqlite3.Connection, puuid: str) -> dict:
    """
    10분 시점 평균 골드차 / CS차.
    timeline_snapshots의 minute=10 행 기준.
    """
    sql = """
        SELECT
            COUNT(*)                        AS games,
            ROUND(AVG(gold_diff), 1)        AS avg_gold_diff_10,
            ROUND(AVG(cs_diff), 2)          AS avg_cs_diff_10,
            SUM(CASE WHEN gold_diff > 0 THEN 1 ELSE 0 END) AS gold_lead_games,
            SUM(CASE WHEN cs_diff   > 0 THEN 1 ELSE 0 END) AS cs_lead_games
        FROM timeline_snapshots
        WHERE puuid = ? AND minute = 10
    """
    cur = conn.execute(sql, (puuid,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else {}


def get_phase_stats(conn: sqlite3.Connection, puuid: str) -> dict:
    """5/10/14/20분 체크포인트별 평균 CS·골드차 (라인전 단계별 성장 지표)."""
    rows = conn.execute("""
        SELECT
            minute,
            ROUND(AVG(cs), 1)         AS avg_cs,
            ROUND(AVG(gold_diff), 1)  AS avg_gold_diff,
            ROUND(AVG(cs_diff), 2)    AS avg_cs_diff,
            COUNT(*)                  AS games
        FROM timeline_snapshots
        WHERE puuid = ? AND minute IN (5, 10, 14, 20)
        GROUP BY minute
        ORDER BY minute
    """, (puuid,)).fetchall()

    result = {}
    for row in rows:
        m = row[0]
        result[f"cs_at_{m}"]      = row[1]
        result[f"gold_diff_{m}"]  = row[2]
        result[f"cs_diff_{m}"]    = row[3]
    return result


def get_gold_diff_by_minute(
    conn: sqlite3.Connection,
    puuid: str,
    max_minute: int = 25
) -> list[dict]:
    """분 단위 평균 골드차 추이 (라인 차트용)"""
    sql = """
        SELECT
            minute,
            ROUND(AVG(gold_diff), 1)    AS avg_gold_diff,
            ROUND(AVG(cs_diff), 2)      AS avg_cs_diff,
            COUNT(*)                    AS sample
        FROM timeline_snapshots
        WHERE puuid = ? AND minute <= ?
        GROUP BY minute
        ORDER BY minute
    """
    cur = conn.execute(sql, (puuid, max_minute))
    return _rows_to_dicts(cur)


# ──────────────────────────────────────────────
# 3. 시야 / 오브젝트
# ──────────────────────────────────────────────

def get_vision_stats(conn: sqlite3.Connection, puuid: str) -> dict:
    """시야 관련 지표"""
    sql = """
        SELECT
            COUNT(*)                                AS games,
            ROUND(AVG(vision_score), 1)             AS avg_vision_score,
            ROUND(AVG(wards_placed), 1)             AS avg_wards_placed,
            ROUND(AVG(wards_killed), 1)             AS avg_wards_killed,
            -- 분당 시야점수 (게임시간 필요 → 매치 JOIN)
            ROUND(
                AVG(CAST(vision_score AS REAL)
                / (m.game_duration / 60.0)), 2
            )                                       AS vision_per_min
        FROM match_participants mp
        JOIN matches m ON mp.match_id = m.match_id
        WHERE mp.puuid = ?
    """
    cur = conn.execute(sql, (puuid,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else {}


# ──────────────────────────────────────────────
# 4. 딜 기여도
# ──────────────────────────────────────────────

def get_damage_stats(conn: sqlite3.Connection, puuid: str) -> dict:
    """딜 기여도 및 피해 비율"""
    sql = """
        WITH team_dmg AS (
            -- 같은 매치에서 같은 팀 총 딜 (win 컬럼으로 팀 구분)
            SELECT
                mp.match_id,
                mp.puuid,
                mp.dmg_dealt,
                mp.dmg_taken,
                SUM(t.dmg_dealt) AS team_total_dmg
            FROM match_participants mp
            JOIN match_participants t
              ON mp.match_id = t.match_id
             AND mp.win      = t.win        -- 같은 팀
            WHERE mp.puuid = ?
            GROUP BY mp.match_id, mp.puuid
        )
        SELECT
            COUNT(*)                                            AS games,
            ROUND(AVG(dmg_dealt), 0)                           AS avg_dmg_dealt,
            ROUND(AVG(dmg_taken), 0)                           AS avg_dmg_taken,
            ROUND(
                AVG(CAST(dmg_dealt AS REAL) / team_total_dmg * 100), 1
            )                                                   AS avg_dmg_share
        FROM team_dmg
    """
    cur = conn.execute(sql, (puuid,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else {}


# ──────────────────────────────────────────────
# 5. 게임별 추이 (라인 차트용)
# ──────────────────────────────────────────────

def get_game_series(
    conn: sqlite3.Connection,
    puuid: str,
    recent_n: Optional[int] = 20
) -> list[dict]:
    """
    최근 N게임의 게임별 주요 지표 (시계열 라인 차트용).
    game_start_ts 기준 내림차순 정렬 후 recent_n개 반환.
    """
    limit_clause = f"LIMIT {recent_n}" if recent_n else ""
    sql = f"""
        SELECT
            mp.match_id,
            m.game_start_ts,
            mp.champion_name,
            mp.position,
            mp.win,
            mp.kills,
            mp.deaths,
            mp.assists,
            ROUND((mp.kills + mp.assists) / MAX(CAST(mp.deaths AS REAL), 1.0), 2) AS kda,
            mp.cs_per_min,
            mp.vision_score,
            mp.kp_percent,
            mp.dmg_dealt
        FROM match_participants mp
        JOIN matches m ON mp.match_id = m.match_id
        WHERE mp.puuid = ?
        ORDER BY m.game_start_ts DESC
        {limit_clause}
    """
    cur = conn.execute(sql, (puuid,))
    return _rows_to_dicts(cur)


# ──────────────────────────────────────────────
# 6. 편의 함수 — 전체 분석 결과 한 번에
# ──────────────────────────────────────────────

LANE_KR = {
    "TOP_LANE": "탑", "MID_LANE": "미드", "BOT_LANE": "봇",
}
MONSTER_KR = {
    "DRAGON": "드래곤", "BARON_NASHOR": "바론", "RIFTHERALD": "전령",
    "RIFTSCUTTLER": "바위게", "HORDE": "공허충",
}


def get_event_stats(conn: sqlite3.Connection, puuid: str) -> dict:
    """이벤트 기반 통계: 첫 귀환 타이밍, 아이템 경로, 오브젝트/포탑 현황"""

    # 첫 귀환 타이밍 (게임 시작 후 1분 초과 첫 아이템 구매 시점)
    first_back = conn.execute("""
        SELECT ROUND(AVG(first_min), 1) AS avg_first_back_min,
               COUNT(*) AS games
        FROM (
            SELECT match_id, MIN(minute) AS first_min
            FROM match_events
            WHERE puuid = ? AND event_type = 'ITEM_PURCHASED' AND minute > 1.0
            GROUP BY match_id
        )
    """, (puuid,)).fetchone()

    # 오브젝트 팀 확보율 (게임당 첫 오브젝트 기준)
    obj_rows = conn.execute("""
        SELECT
            fo.monster_type,
            COUNT(*)                                                              AS total_games,
            ROUND(AVG(fo.first_min), 1)                                          AS avg_minute,
            SUM(CASE WHEN fo.first_team = mpt.team_id THEN 1 ELSE 0 END)        AS team_secured
        FROM (
            SELECT match_id, monster_type,
                   MIN(minute)        AS first_min,
                   MIN(killer_team_id) AS first_team
            FROM match_events
            WHERE event_type = 'ELITE_MONSTER_KILL'
              AND monster_type IN ('DRAGON','BARON_NASHOR','RIFTHERALD','HORDE')
            GROUP BY match_id, monster_type
        ) fo
        JOIN match_player_teams mpt ON fo.match_id = mpt.match_id AND mpt.puuid = ?
        GROUP BY fo.monster_type
        ORDER BY AVG(fo.first_min)
    """, (puuid,)).fetchall()

    # 라인별 첫 포탑 — 게임당 각 라인의 첫 포탑만 추림
    tower_rows = conn.execute("""
        SELECT
            ft.lane_type,
            COUNT(*)                                                            AS total_games,
            ROUND(AVG(ft.minute), 1)                                            AS avg_minute,
            SUM(CASE WHEN ft.team_id != mpt.team_id THEN 1 ELSE 0 END)         AS my_team_first
        FROM (
            SELECT match_id, lane_type, MIN(minute) AS minute,
                   MIN(team_id) AS team_id
            FROM match_events
            WHERE event_type = 'BUILDING_KILL' AND building_type = 'TOWER_BUILDING'
            GROUP BY match_id, lane_type
        ) ft
        JOIN match_player_teams mpt ON ft.match_id = mpt.match_id AND mpt.puuid = ?
        WHERE ft.lane_type IS NOT NULL
        GROUP BY ft.lane_type
    """, (puuid,)).fetchall()

    # 최근 20게임 아이템 구매 이력 (시작템·와드 제외, 분당 정렬)
    item_rows = conn.execute("""
        SELECT me.match_id, me.minute, me.item_id
        FROM match_events me
        JOIN matches m ON me.match_id = m.match_id
        WHERE me.puuid = ? AND me.event_type = 'ITEM_PURCHASED'
          AND me.minute > 1.0
          AND me.match_id IN (
              SELECT mp.match_id FROM match_participants mp
              JOIN matches m2 ON mp.match_id = m2.match_id
              WHERE mp.puuid = ?
              ORDER BY m2.game_start_ts DESC LIMIT 20
          )
        ORDER BY m.game_start_ts DESC, me.timestamp_ms
    """, (puuid, puuid)).fetchall()

    objectives = [
        {
            "type": row[0],
            "type_kr": MONSTER_KR.get(row[0], row[0]),
            "total_games": row[1],
            "avg_minute": row[2],
            "team_secured": row[3],
            "secure_rate": round(row[3] / row[1] * 100, 1) if row[1] else 0,
        }
        for row in obj_rows
    ]

    towers = [
        {
            "lane": row[0],
            "lane_kr": LANE_KR.get(row[0], row[0]),
            "total_games": row[1],
            "avg_minute": row[2],
            "my_team_first": row[3],
            "first_rate": round(row[3] / row[1] * 100, 1) if row[1] else 0,
        }
        for row in tower_rows
    ]

    items_by_match: dict[str, list] = {}
    for row in item_rows:
        items_by_match.setdefault(row[0], []).append({"minute": row[1], "item_id": row[2]})

    return {
        "avg_first_back_min": dict(first_back)["avg_first_back_min"] if first_back else None,
        "first_back_games":   dict(first_back)["games"] if first_back else 0,
        "objectives":         objectives,
        "towers":             towers,
        "items_by_match":     items_by_match,
    }


def get_full_analysis(conn: sqlite3.Connection, puuid: str) -> dict:
    """
    모든 분석 지표를 dict로 묶어서 반환.
    Claude API 프롬프트 구성 시 이 함수 하나만 호출하면 됨.
    """
    return {
        "overall":    get_overall_stats(conn, puuid),
        "champions":  get_champion_stats(conn, puuid),
        "positions":  get_position_stats(conn, puuid),
        "laning":     get_laning_stats(conn, puuid),
        "phase":      get_phase_stats(conn, puuid),
        "gold_curve": get_gold_diff_by_minute(conn, puuid),
        "vision":     get_vision_stats(conn, puuid),
        "damage":     get_damage_stats(conn, puuid),
        "series":     get_game_series(conn, puuid, recent_n=20),
        "events":     get_event_stats(conn, puuid),
    }