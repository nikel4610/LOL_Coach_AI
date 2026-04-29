# src/meta/champion_roles.py
"""
챔피언 역할군 3레이어 구성 + DB 저장.

레이어 1: Riot 공식 tags (champion_info)
레이어 2: 실제 수집 데이터 포지션 집계 (champion_position_stats)
레이어 3: data/champion_overrides.json 수동 오버라이드

사용법:
    python -m src.meta.champion_roles          # 전체 실행
    python -m src.meta.champion_roles --dry-run
"""

import sqlite3
import json
import argparse
from pathlib import Path


# ──────────────────────────────────────────────
# 수동 오버라이드 기본값 (JSON 없을 때 폴백)
# ──────────────────────────────────────────────

DEFAULT_OVERRIDES = {
    "splitpusher":  ["Fiora", "Tryndamere", "Yorick", "Camille", "Garen",
                     "Nasus", "Illaoi", "Sion"],
    "engage_tank":  ["Malphite", "Ornn", "Leona", "Nautilus", "Amumu",
                     "Jarvan IV", "Zac", "Sejuani", "Galio"],
    "utility_tank": ["Shen", "Taric", "TahmKench"],
    "poke_mage":    ["Jayce", "Rumble", "Kennen", "Gangplank"],
    "battlemage":   ["Sylas", "Mordekaiser", "Cassiopeia", "Vladimir",
                     "Swain", "Rumble"],
    "enchanter":    ["Lulu", "Janna", "Soraka", "Nami", "Yuumi",
                     "Renata Glasc", "Karma", "Sona"],
    "engage_support":["Thresh", "Blitzcrank", "Alistar", "Leona",
                      "Nautilus", "Rell", "Pyke"],
}


# ──────────────────────────────────────────────
# DB 테이블 생성
# ──────────────────────────────────────────────

CREATE_POSITION_STATS_SQL = """
    CREATE TABLE IF NOT EXISTS champion_position_stats (
        champion_id     TEXT NOT NULL,
        position        TEXT NOT NULL,
        games           INTEGER DEFAULT 0,
        wins            INTEGER DEFAULT 0,
        pick_rate       REAL,   -- 해당 포지션에서 픽률 (%)
        win_rate        REAL,   -- 해당 포지션에서 승률 (%)
        patch_version   TEXT NOT NULL,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (champion_id, position, patch_version)
    );
"""

CREATE_CHAMPION_ROLES_SQL = """
    CREATE TABLE IF NOT EXISTS champion_roles (
        champion_id     TEXT PRIMARY KEY,
        champion_name   TEXT,
        riot_primary    TEXT,           -- 레이어 1: Riot 공식 1차 태그
        riot_secondary  TEXT,           -- 레이어 1: Riot 공식 2차 태그
        main_position   TEXT,           -- 레이어 2: 실제 데이터 주 포지션
        sub_position    TEXT,           -- 레이어 2: 2번째 포지션
        role_override   TEXT,           -- 레이어 3: 수동 오버라이드
        final_role      TEXT,           -- 최종 역할군 (override > riot_primary)
        patch_version   TEXT,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


# ──────────────────────────────────────────────
# 레이어 2: 실제 데이터 포지션 집계
# ──────────────────────────────────────────────

def compute_position_stats(
    conn: sqlite3.Connection,
    patch_version: str
) -> list[dict]:
    """
    match_participants에서 챔피언별 포지션 픽률/승률 집계.
    champion_info에 있는 챔피언만 대상 (티어없음 참가자 제외).
    """
    sql = """
        WITH champ_pos AS (
            SELECT
                mp.champion_name,
                mp.position,
                COUNT(*)        AS games,
                SUM(mp.win)     AS wins
            FROM match_participants mp
            JOIN summoners s ON mp.puuid = s.puuid
            WHERE s.tier IS NOT NULL
              AND mp.position IS NOT NULL
              AND mp.position != ''
              AND mp.champion_name IS NOT NULL
            GROUP BY mp.champion_name, mp.position
        ),
        champ_total AS (
            SELECT champion_name, SUM(games) AS total_games
            FROM champ_pos
            GROUP BY champion_name
        )
        SELECT
            ci.champion_id,
            cp.champion_name,
            cp.position,
            cp.games,
            cp.wins,
            ROUND(CAST(cp.games AS REAL) / ct.total_games * 100, 1) AS pick_rate,
            ROUND(CAST(cp.wins  AS REAL) / cp.games       * 100, 1) AS win_rate
        FROM champ_pos cp
        JOIN champ_total ct ON cp.champion_name = ct.champion_name
        LEFT JOIN champion_info ci ON cp.champion_name = ci.champion_id
        ORDER BY cp.champion_name, cp.games DESC
    """
    rows = conn.execute(sql).fetchall()
    cols = ["champion_id", "champion_name", "position",
            "games", "wins", "pick_rate", "win_rate"]
    return [{**dict(zip(cols, r)), "patch_version": patch_version} for r in rows]


def get_main_positions(position_stats: list[dict]) -> dict[str, tuple]:
    """
    포지션 통계에서 챔피언별 주/부 포지션 추출.
    반환: {champion_id: (main_position, sub_position)}
    """
    from collections import defaultdict
    champ_pos = defaultdict(list)
    for row in position_stats:
        champ_pos[row["champion_id"]].append((row["position"], row["games"]))

    result = {}
    for champ_id, pos_list in champ_pos.items():
        sorted_pos = sorted(pos_list, key=lambda x: -x[1])
        main = sorted_pos[0][0] if len(sorted_pos) > 0 else None
        sub  = sorted_pos[1][0] if len(sorted_pos) > 1 else None
        result[champ_id] = (main, sub)
    return result


# ──────────────────────────────────────────────
# 레이어 3: 수동 오버라이드 로드
# ──────────────────────────────────────────────

def load_overrides(override_path: str = "data/champion_overrides.json") -> dict[str, str]:
    """
    champion_overrides.json 로드.
    반환: {champion_id: role_override}
    없으면 DEFAULT_OVERRIDES 사용.
    """
    path = Path(override_path)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = DEFAULT_OVERRIDES
        # 파일 없으면 기본값으로 생성
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_OVERRIDES, f, ensure_ascii=False, indent=2)
        print(f"[오버라이드] {override_path} 파일 생성 (기본값)")

    # {role: [champ, ...]} → {champ: role} 역변환
    champ_to_role = {}
    for role, champs in raw.items():
        for champ in champs:
            champ_to_role[champ] = role
    return champ_to_role


# ──────────────────────────────────────────────
# 3레이어 합성 → champion_roles 구성
# ──────────────────────────────────────────────

def build_champion_roles(
    conn: sqlite3.Connection,
    patch_version: str,
    override_path: str = "data/champion_overrides.json",
) -> list[dict]:
    """
    3레이어를 합성해 champion_roles 행 목록 반환.
    """
    # 레이어 1: Riot 공식 tags
    riot_tags = {
        row[0]: {"champion_name": row[1], "primary": row[2], "secondary": row[3]}
        for row in conn.execute(
            "SELECT champion_id, champion_name, primary_tag, secondary_tag "
            "FROM champion_info WHERE patch_version = ?",
            (patch_version,)
        ).fetchall()
    }

    # 레이어 2: 실제 데이터 주/부 포지션
    position_stats = compute_position_stats(conn, patch_version)
    main_positions = get_main_positions(position_stats)

    # 레이어 3: 수동 오버라이드
    overrides = load_overrides(override_path)

    # 합성
    rows = []
    for champ_id, tags in riot_tags.items():
        main_pos, sub_pos = main_positions.get(champ_id, (None, None))
        override = overrides.get(champ_id) or overrides.get(tags["champion_name"])
        final_role = override if override else tags["primary"]

        rows.append({
            "champion_id":    champ_id,
            "champion_name":  tags["champion_name"],
            "riot_primary":   tags["primary"],
            "riot_secondary": tags["secondary"],
            "main_position":  main_pos,
            "sub_position":   sub_pos,
            "role_override":  override,
            "final_role":     final_role,
            "patch_version":  patch_version,
        })

    rows.sort(key=lambda x: x["champion_id"])
    return rows, position_stats


# ──────────────────────────────────────────────
# DB 저장
# ──────────────────────────────────────────────

def save_champion_roles(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.execute(CREATE_CHAMPION_ROLES_SQL)
    sql = """
        INSERT INTO champion_roles (
            champion_id, champion_name, riot_primary, riot_secondary,
            main_position, sub_position, role_override, final_role,
            patch_version, updated_at
        ) VALUES (
            :champion_id, :champion_name, :riot_primary, :riot_secondary,
            :main_position, :sub_position, :role_override, :final_role,
            :patch_version, CURRENT_TIMESTAMP
        )
        ON CONFLICT(champion_id) DO UPDATE SET
            riot_primary   = excluded.riot_primary,
            riot_secondary = excluded.riot_secondary,
            main_position  = excluded.main_position,
            sub_position   = excluded.sub_position,
            role_override  = excluded.role_override,
            final_role     = excluded.final_role,
            patch_version  = excluded.patch_version,
            updated_at     = CURRENT_TIMESTAMP
    """
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def save_position_stats(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.execute(CREATE_POSITION_STATS_SQL)
    sql = """
        INSERT INTO champion_position_stats (
            champion_id, position, games, wins,
            pick_rate, win_rate, patch_version, updated_at
        ) VALUES (
            :champion_id, :position, :games, :wins,
            :pick_rate, :win_rate, :patch_version, CURRENT_TIMESTAMP
        )
        ON CONFLICT(champion_id, position, patch_version) DO UPDATE SET
            games      = excluded.games,
            wins       = excluded.wins,
            pick_rate  = excluded.pick_rate,
            win_rate   = excluded.win_rate,
            updated_at = CURRENT_TIMESTAMP
    """
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="챔피언 역할군 3레이어 구성")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", default="data/lol_coach.db")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    patch = conn.execute(
        "SELECT game_version FROM matches ORDER BY game_start_ts DESC LIMIT 1"
    ).fetchone()[0]
    print(f"[패치 버전] {patch}")

    # champion_info 패치 버전은 Data Dragon 기준이라 다를 수 있음
    dd_patch = conn.execute(
        "SELECT patch_version FROM champion_info LIMIT 1"
    ).fetchone()[0]
    print(f"[Data Dragon 버전] {dd_patch}")

    role_rows, pos_stats = build_champion_roles(conn, dd_patch)
    print(f"\n[역할군 행] {len(role_rows)}개 챔피언")
    print(f"[포지션 통계] {len(pos_stats)}개 행")

    # 결과 미리보기
    print("\n[샘플 — 역할군 확인]")
    for r in role_rows[:10]:
        override_mark = f" → override:{r['role_override']}" if r["role_override"] else ""
        print(f"  {r['champion_id']:<15} {r['champion_name']:<8} "
              f"riot:{r['riot_primary']:<10} "
              f"pos:{r['main_position'] or '-':<8}"
              f"{override_mark}")

    # 데이터 있는 챔피언만 따로 출력
    has_data = [r for r in role_rows if r["main_position"]]
    print(f"\n[실제 데이터 있는 챔피언] {len(has_data)}개")
    for r in has_data[:10]:
        print(f"  {r['champion_name']:<8} 주포지션:{r['main_position']:<8} "
              f"부포지션:{r['sub_position'] or '-':<8} "
              f"최종역할군:{r['final_role']}")

    if args.dry_run:
        print("\n[dry-run] DB 저장 생략")
        conn.close()
        return

    saved_roles = save_champion_roles(conn, role_rows)
    pos_stats_valid = [r for r in pos_stats if r.get("champion_id") is not None]
    print(f"[포지션 통계 유효] {len(pos_stats_valid)}행 (전체 {len(pos_stats)}행 중)")
    saved_pos = save_position_stats(conn, pos_stats_valid)
    print(f"\n[저장 완료] champion_roles {saved_roles}행 / "
          f"champion_position_stats {saved_pos}행")
    conn.close()


if __name__ == "__main__":
    main()