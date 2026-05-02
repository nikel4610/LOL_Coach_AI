-- LoL Coach AI Database Schema
-- SQLite (로컬 개발) / PostgreSQL (배포) 동일 구조
-- 생성: python -m src.db.init_db

-- ── 소환사 정보 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS summoners (
    puuid           TEXT PRIMARY KEY,
    game_name       TEXT NOT NULL,
    tag_line        TEXT NOT NULL,
    summoner_level  INTEGER,
    profile_icon_id INTEGER,
    tier            TEXT,       -- IRON / BRONZE / SILVER / ...
    rank            TEXT,       -- I / II / III / IV
    lp              INTEGER,
    wins            INTEGER,
    losses          INTEGER,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── 매치 기본 정보 ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matches (
    match_id        TEXT PRIMARY KEY,
    game_duration   INTEGER,    -- 초 단위
    game_version    TEXT,       -- 패치 버전 (예: 16.8.1)
    queue_id        INTEGER,    -- 420 = 솔로랭크
    game_start_ts   INTEGER,    -- Unix timestamp (ms)
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── 매치 참가자 성과 ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS match_participants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT NOT NULL REFERENCES matches(match_id),
    puuid           TEXT NOT NULL REFERENCES summoners(puuid),
    champion_id     INTEGER,
    champion_name   TEXT,
    position        TEXT,       -- TOP / JUNGLE / MIDDLE / BOTTOM / UTILITY
    win             INTEGER,    -- 1 = 승, 0 = 패
    kills           INTEGER,
    deaths          INTEGER,
    assists         INTEGER,
    cs_total        INTEGER,    -- 미니언 + 중립 몬스터
    cs_per_min      REAL,
    gold_earned     INTEGER,
    vision_score    INTEGER,
    wards_placed    INTEGER,
    wards_killed    INTEGER,
    kp_percent      REAL,       -- 킬 관여율 (%)
    dmg_dealt       INTEGER,    -- 챔피언에게 가한 피해
    dmg_taken       INTEGER,    -- 받은 피해
    UNIQUE(match_id, puuid)
);

-- ── 분당 타임라인 스냅샷 ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS timeline_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT NOT NULL REFERENCES matches(match_id),
    puuid           TEXT NOT NULL,
    minute          INTEGER NOT NULL,   -- 0, 1, 2, ... (분)
    gold            INTEGER,
    cs              INTEGER,
    xp              INTEGER,
    gold_diff       INTEGER,    -- vs 상대 라이너 (양수 = 유리)
    cs_diff         INTEGER,    -- vs 상대 라이너
    UNIQUE(match_id, puuid, minute)
);

-- ── 티어 평균 집계 캐시 ───────────────────────────────────────
-- 배치 집계 결과를 저장해두고 빠르게 비교에 활용
CREATE TABLE IF NOT EXISTS tier_averages (
    tier            TEXT NOT NULL,
    position        TEXT NOT NULL,
    metric          TEXT NOT NULL,  -- cs_per_min / kp_percent / vision_score / ...
    avg_value       REAL,
    sample_count    INTEGER,
    patch_version   TEXT NOT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tier, position, metric, patch_version)
);

-- ── 게임 이벤트 ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS match_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT    NOT NULL,
    puuid           TEXT,               -- 이벤트 주체 puuid (미니언 킬 등은 NULL)
    timestamp_ms    INTEGER NOT NULL,
    minute          REAL    NOT NULL,
    phase           TEXT,               -- early / mid / late
    event_type      TEXT    NOT NULL,   -- ITEM_PURCHASED / BUILDING_KILL / ELITE_MONSTER_KILL
    item_id         INTEGER,
    lane_type       TEXT,               -- TOP_LANE / MID_LANE / BOT_LANE
    building_type   TEXT,               -- TOWER_BUILDING / INHIBITOR_BUILDING
    team_id         INTEGER,            -- 포탑 소유 팀 (파괴된 팀)
    monster_type    TEXT,               -- DRAGON / BARON_NASHOR / RIFTHERALD / RIFTSCUTTLER / HORDE
    monster_sub_type TEXT,
    killer_team_id  INTEGER
);

-- 매치별 puuid → team_id (100=블루 / 200=레드) 매핑
CREATE TABLE IF NOT EXISTS match_player_teams (
    match_id    TEXT NOT NULL,
    puuid       TEXT NOT NULL,
    team_id     INTEGER NOT NULL,
    PRIMARY KEY (match_id, puuid)
);

-- ── 인덱스 ────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_participants_puuid
    ON match_participants(puuid);

CREATE INDEX IF NOT EXISTS idx_participants_match
    ON match_participants(match_id);

CREATE INDEX IF NOT EXISTS idx_timeline_match_puuid
    ON timeline_snapshots(match_id, puuid);

CREATE INDEX IF NOT EXISTS idx_tier_avg_lookup
    ON tier_averages(tier, position, patch_version);
