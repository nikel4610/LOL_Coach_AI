"""
타임라인 이벤트 파서
data/raw/timelines/ JSON을 파싱해 구조화된 이벤트 데이터를 반환한다.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── 오브젝트 고정 스폰 타이밍 (ms) ────────────────────────────────────────

OBJECTIVE_SPAWN = {
    "DRAGON":       5 * 60 * 1000,   # 5:00
    "RIFTHERALD":   8 * 60 * 1000,   # 8:00
    "BARON_NASHOR": 20 * 60 * 1000,  # 20:00
}
OBJECTIVE_RESPAWN = {
    "DRAGON":       5 * 60 * 1000,   # 킬 후 5분
    "RIFTHERALD":   6 * 60 * 1000,   # 킬 후 6분
    "BARON_NASHOR": 6 * 60 * 1000,   # 킬 후 6분
}
HERALD_DESPAWN_MS = 19 * 60 * 1000 + 45 * 1000  # 19:45 소멸

# ── 상수 ───────────────────────────────────────────────────────────────────

TIMELINE_DIR = Path("data/raw/timelines")
HERALD_DESPAWN_MS = 19 * 60 * 1000 + 45 * 1000  # 19:45

# 게임 단계 기준 (ms)
PHASE_EARLY_END_MS  = 14 * 60 * 1000   # 14분
PHASE_MID_END_MS    = 20 * 60 * 1000   # 20분

# 파싱 대상 이벤트 타입
TARGET_EVENTS = {
    "ELITE_MONSTER_KILL",
    "DRAGON_SOUL_GIVEN",
    "BUILDING_KILL",
    "TURRET_PLATE_DESTROYED",
    "CHAMPION_KILL",
    "CHAMPION_SPECIAL_KILL",
    "ITEM_PURCHASED",
    "ITEM_SOLD",
    "ITEM_DESTROYED",
    "ITEM_UNDO",
    "LEVEL_UP",
    "SKILL_LEVEL_UP",
    "WARD_PLACED",
    "WARD_KILL",
}

# 핵심 완성 아이템 ID (코어 아이템 완성 감지용)
# TODO: Data Dragon 아이템 데이터 연동 후 확장
CORE_ITEM_IDS: set[int] = set()  # 현재는 필터 없이 전체 수집


# ── 데이터 클래스 ───────────────────────────────────────────────────────────

@dataclass
class ParsedEvent:
    """파싱된 단일 이벤트"""
    timestamp_ms: int
    timestamp_min: float          # 분 단위 (소수점)
    phase: str                    # early / mid / late
    event_type: str
    participant_id: Optional[int] = None
    killer_id: Optional[int]      = None
    victim_id: Optional[int]      = None
    assisting_ids: list[int]      = field(default_factory=list)
    monster_type: Optional[str]   = None
    monster_sub_type: Optional[str] = None
    building_type: Optional[str]  = None
    tower_type: Optional[str]     = None
    lane_type: Optional[str]      = None
    team_id: Optional[int]        = None
    killer_team_id: Optional[int] = None
    item_id: Optional[int]        = None
    level: Optional[int]          = None
    skill_slot: Optional[int]     = None
    kill_type: Optional[str]      = None  # FIRST_BLOOD, ACE 등
    ward_type: Optional[str]      = None
    bounty: Optional[int]         = None
    position: Optional[dict]      = None


@dataclass
class GamePhases:
    match_id: str
    early: list[ParsedEvent]  = field(default_factory=list)
    mid:   list[ParsedEvent]  = field(default_factory=list)
    late:  list[ParsedEvent]  = field(default_factory=list)
    all:   list[ParsedEvent]  = field(default_factory=list)

    # 킬 타이밍 (기존)
    first_dragon_kill_ms:  Optional[int] = None
    first_baron_kill_ms:   Optional[int] = None
    first_herald_kill_ms:  Optional[int] = None
    first_tower_ms:        Optional[int] = None
    first_blood_ms:        Optional[int] = None
    dragon_soul_team:      Optional[int] = None

    # 스폰 타이밍 (역산)
    dragon_spawns_ms:  list[int] = field(default_factory=list)  # 스폰된 시점 목록
    baron_spawns_ms:   list[int] = field(default_factory=list)
    herald_spawns_ms:  list[int] = field(default_factory=list)


# ── 내부 헬퍼 ──────────────────────────────────────────────────────────────

def _ms_to_min(ms: int) -> float:
    return round(ms / 60_000, 2)


def _get_phase(ms: int) -> str:
    if ms < PHASE_EARLY_END_MS:
        return "early"
    if ms < PHASE_MID_END_MS:
        return "mid"
    return "late"


def _parse_event(raw: dict) -> Optional[ParsedEvent]:
    """단일 raw 이벤트 → ParsedEvent. 파싱 불필요 타입은 None 반환."""
    event_type = raw.get("type", "")
    if event_type not in TARGET_EVENTS:
        return None

    ts = raw.get("timestamp", 0)

    return ParsedEvent(
        timestamp_ms   = ts,
        timestamp_min  = _ms_to_min(ts),
        phase          = _get_phase(ts),
        event_type     = event_type,
        participant_id = raw.get("participantId"),
        killer_id      = raw.get("killerId"),
        victim_id      = raw.get("victimId"),
        assisting_ids  = raw.get("assistingParticipantIds", []),
        monster_type   = raw.get("monsterType"),
        monster_sub_type = raw.get("monsterSubType"),
        building_type  = raw.get("buildingType"),
        tower_type     = raw.get("towerType"),
        lane_type      = raw.get("laneType"),
        team_id        = raw.get("teamId"),
        killer_team_id = raw.get("killerTeamId"),
        item_id        = raw.get("itemId"),
        level          = raw.get("level"),
        skill_slot     = raw.get("skillSlot"),
        kill_type      = raw.get("killType"),
        ward_type      = raw.get("wardType"),
        bounty         = raw.get("bounty"),
        position       = raw.get("position"),
    )

def _fill_summary(phases: GamePhases, game_end_ms: int) -> None:
    dragon_kills: list[int] = []
    baron_kills:  list[int] = []
    herald_kills: list[int] = []

    for e in phases.all:
        t = e.event_type

        if t == "CHAMPION_SPECIAL_KILL" and e.kill_type == "KILL_FIRST_BLOOD":
            if phases.first_blood_ms is None:
                phases.first_blood_ms = e.timestamp_ms

        elif t == "ELITE_MONSTER_KILL":
            mt = e.monster_type
            if mt == "DRAGON":
                dragon_kills.append(e.timestamp_ms)
                if phases.first_dragon_kill_ms is None:
                    phases.first_dragon_kill_ms = e.timestamp_ms
            elif mt == "BARON_NASHOR":
                baron_kills.append(e.timestamp_ms)
                if phases.first_baron_kill_ms is None:
                    phases.first_baron_kill_ms = e.timestamp_ms
            elif mt == "RIFTHERALD":
                herald_kills.append(e.timestamp_ms)
                if phases.first_herald_kill_ms is None:
                    phases.first_herald_kill_ms = e.timestamp_ms

        elif t == "BUILDING_KILL" and e.building_type == "TOWER_BUILDING":
            if phases.first_tower_ms is None:
                phases.first_tower_ms = e.timestamp_ms

        elif t == "DRAGON_SOUL_GIVEN":
            phases.dragon_soul_team = e.team_id

        elif t == "GAME_END":  # [추가]
            game_end_ms = e.timestamp_ms

    # 스폰 역산
    phases.dragon_spawns_ms = _calc_spawns(
        dragon_kills,
        first_spawn_ms=OBJECTIVE_SPAWN["DRAGON"],
        respawn_ms=OBJECTIVE_RESPAWN["DRAGON"],
        game_end_ms=game_end_ms,
    )
    phases.baron_spawns_ms = _calc_spawns(
        baron_kills,
        first_spawn_ms=OBJECTIVE_SPAWN["BARON_NASHOR"],
        respawn_ms=OBJECTIVE_RESPAWN["BARON_NASHOR"],
        game_end_ms=game_end_ms,
    )
    phases.herald_spawns_ms = _calc_spawns(
        herald_kills,
        first_spawn_ms=OBJECTIVE_SPAWN["RIFTHERALD"],
        respawn_ms=OBJECTIVE_RESPAWN["RIFTHERALD"],
        game_end_ms=game_end_ms,
        despawn_ms=HERALD_DESPAWN_MS,
    )

def _calc_spawns(
    kill_times_ms: list[int],
    first_spawn_ms: int,
    respawn_ms: int,
    game_end_ms: int,
    despawn_ms: Optional[int] = None,
) -> list[int]:
    """
    킬 이력으로 스폰 시점 목록을 역산한다.
    - 킬 없이도 respawn_ms 주기로 자동 스폰
    - 킬이 현재 스폰 이후에 발생한 경우에만 '킬 + respawn' 으로 다음 스폰 계산
    - game_end_ms 이후 스폰은 제외
    - despawn_ms 이후 스폰은 제외 (전령용)
    """
    spawns = [first_spawn_ms]
    current_spawn = first_spawn_ms
    kill_idx = 0

    while True:
        # 현재 스폰에 대응하는 킬 탐색
        # (현재 스폰 이후에 발생한 킬 중 가장 빠른 것)
        kill_ms = None
        while kill_idx < len(kill_times_ms):
            if kill_times_ms[kill_idx] >= current_spawn:
                kill_ms = kill_times_ms[kill_idx]
                kill_idx += 1
                break
            kill_idx += 1

        # 다음 스폰 시점 결정
        if kill_ms is not None:
            next_spawn = kill_ms + respawn_ms
        else:
            # 킬 없음 → 자연 주기로 다음 스폰
            next_spawn = current_spawn + respawn_ms

        # 종료 조건
        if next_spawn > game_end_ms:
            break
        if despawn_ms and next_spawn >= despawn_ms:
            break

        spawns.append(next_spawn)
        current_spawn = next_spawn

    return spawns

# ── 공개 API ───────────────────────────────────────────────────────────────

def parse_timeline(match_id: str) -> Optional[GamePhases]:
    path = TIMELINE_DIR / f"{match_id}.json"
    if not path.exists():
        print(f"[event_parser] 파일 없음: {path}")
        return None

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    frames = data.get("info", {}).get("frames", [])
    phases = GamePhases(match_id=match_id)

    # [수정] GAME_END는 별도 추출, TARGET_EVENTS 통해 수집 안 함
    game_end_ms = 0

    for frame in frames:
        for raw_event in frame.get("events", []):
            # GAME_END 별도 처리
            if raw_event.get("type") == "GAME_END":
                game_end_ms = raw_event.get("timestamp", 0)
                continue

            event = _parse_event(raw_event)
            if event is None:
                continue

            phases.all.append(event)
            if event.phase == "early":
                phases.early.append(event)
            elif event.phase == "mid":
                phases.mid.append(event)
            else:
                phases.late.append(event)

    _fill_summary(phases, game_end_ms)  # [수정] game_end_ms 직접 전달

    print(
        f"[event_parser] {match_id} | "
        f"전체 {len(phases.all)}건 "
        f"(초반 {len(phases.early)} / 중반 {len(phases.mid)} / 후반 {len(phases.late)})"
    )
    return phases


def parse_all_timelines() -> dict[str, GamePhases]:
    """
    data/raw/timelines/ 내 모든 JSON을 파싱한다.

    Returns:
        {match_id: GamePhases} 딕셔너리
    """
    results: dict[str, GamePhases] = {}
    files = sorted(TIMELINE_DIR.glob("*.json"))
    print(f"[event_parser] 타임라인 파일 {len(files)}개 발견")

    for f in files:
        match_id = f.stem
        phases = parse_timeline(match_id)
        if phases:
            results[match_id] = phases

    print(f"[event_parser] 파싱 완료: {len(results)}게임")
    return results

def get_phase_summary(phases: GamePhases) -> dict:
    from collections import Counter

    def count_by_type(events: list[ParsedEvent]) -> dict:
        return dict(Counter(e.event_type for e in events))

    def ms_to_str(ms: Optional[int]) -> Optional[str]:
        if ms is None:
            return None
        m, s = divmod(ms // 1000, 60)
        return f"{m}:{s:02d}"

    def ms_list_to_str(ms_list: list[int]) -> list[str]:
        return [ms_to_str(ms) for ms in ms_list]

    return {
        "match_id": phases.match_id,
        "key_timings": {
            "first_blood":      ms_to_str(phases.first_blood_ms),
            "first_tower":      ms_to_str(phases.first_tower_ms),
            "first_dragon_kill": ms_to_str(phases.first_dragon_kill_ms),
            "first_baron_kill":  ms_to_str(phases.first_baron_kill_ms),
            "first_herald_kill": ms_to_str(phases.first_herald_kill_ms),
            "dragon_soul_team":  phases.dragon_soul_team,
        },
        "objective_spawns": {
            "dragon":  ms_list_to_str(phases.dragon_spawns_ms),
            "baron":   ms_list_to_str(phases.baron_spawns_ms),
            "herald":  ms_list_to_str(phases.herald_spawns_ms),
        },
        "event_counts": {
            "early": count_by_type(phases.early),
            "mid":   count_by_type(phases.mid),
            "late":  count_by_type(phases.late),
        },
    }