"""
타임라인 JSON → match_events / match_player_teams DB 저장.
"""

import json
from pathlib import Path

TIMELINE_DIR = Path("data/raw/timelines")

PHASE_EARLY_END_MS = 14 * 60 * 1000
PHASE_MID_END_MS   = 20 * 60 * 1000

TARGET_MONSTER_TYPES = {
    "DRAGON", "BARON_NASHOR", "RIFTHERALD", "RIFTSCUTTLER", "HORDE",
}


def _phase(ms: int) -> str:
    if ms < PHASE_EARLY_END_MS:
        return "early"
    if ms < PHASE_MID_END_MS:
        return "mid"
    return "late"


def parse_timeline_events(match_id: str) -> tuple[list[dict], list[dict]]:
    """
    타임라인 JSON 1개 파싱.

    반환:
        (events, team_assignments)
        - events: match_events 테이블에 저장할 이벤트 목록
        - team_assignments: match_player_teams 테이블에 저장할 puuid→team 매핑
    """
    path = TIMELINE_DIR / f"{match_id}.json"
    if not path.exists():
        return [], []

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    info = data.get("info", {})
    participants = info.get("participants", [])

    # participantId 1-5 = 팀100(블루), 6-10 = 팀200(레드)
    pid_to_puuid = {p["participantId"]: p["puuid"] for p in participants if "participantId" in p and "puuid" in p}
    pid_to_team  = {pid: (100 if pid <= 5 else 200) for pid in pid_to_puuid}

    team_assignments = [
        {"match_id": match_id, "puuid": puuid, "team_id": pid_to_team[pid]}
        for pid, puuid in pid_to_puuid.items()
    ]

    events = []
    for frame in info.get("frames", []):
        for e in frame.get("events", []):
            event_type = e.get("type", "")
            ms  = e.get("timestamp", 0)
            min_ = round(ms / 60000, 2)
            phase = _phase(ms)

            row = None

            if event_type == "ITEM_PURCHASED":
                pid   = e.get("participantId")
                puuid = pid_to_puuid.get(pid)
                if puuid:
                    row = {
                        "event_type":  event_type,
                        "puuid":       puuid,
                        "item_id":     e.get("itemId"),
                    }

            elif event_type == "BUILDING_KILL" and e.get("buildingType") == "TOWER_BUILDING":
                killer_pid = e.get("killerId")
                puuid = pid_to_puuid.get(killer_pid)  # 미니언 킬이면 None
                row = {
                    "event_type":   event_type,
                    "puuid":        puuid,
                    "lane_type":    e.get("laneType"),
                    "building_type": e.get("buildingType"),
                    "team_id":      e.get("teamId"),  # 포탑 소유팀(파괴당한 팀)
                }

            elif event_type == "ELITE_MONSTER_KILL":
                monster_type = e.get("monsterType", "")
                if monster_type in TARGET_MONSTER_TYPES:
                    killer_pid = e.get("killerId")
                    puuid = pid_to_puuid.get(killer_pid)
                    row = {
                        "event_type":      event_type,
                        "puuid":           puuid,
                        "monster_type":    monster_type,
                        "monster_sub_type": e.get("monsterSubType"),
                        "killer_team_id":  e.get("killerTeamId"),
                    }

            if row:
                row["match_id"]     = match_id
                row["timestamp_ms"] = ms
                row["minute"]       = min_
                row["phase"]        = phase
                events.append(row)

    return events, team_assignments


def save_events(conn, events: list[dict], team_assignments: list[dict]) -> int:
    """match_events / match_player_teams 테이블에 저장."""
    if not events and not team_assignments:
        return 0

    event_sql = """
        INSERT INTO match_events
            (match_id, puuid, timestamp_ms, minute, phase, event_type,
             item_id, lane_type, building_type, team_id,
             monster_type, monster_sub_type, killer_team_id)
        VALUES
            (:match_id, :puuid, :timestamp_ms, :minute, :phase, :event_type,
             :item_id, :lane_type, :building_type, :team_id,
             :monster_type, :monster_sub_type, :killer_team_id)
    """
    team_sql = """
        INSERT OR IGNORE INTO match_player_teams (match_id, puuid, team_id)
        VALUES (:match_id, :puuid, :team_id)
    """

    _KEYS = ("match_id", "puuid", "timestamp_ms", "minute", "phase", "event_type",
             "item_id", "lane_type", "building_type", "team_id",
             "monster_type", "monster_sub_type", "killer_team_id")
    normalized = [{k: e.get(k) for k in _KEYS} for e in events]

    conn.executemany(event_sql, normalized)
    conn.executemany(team_sql, team_assignments)
    return len(events)
