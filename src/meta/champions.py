# src/meta/champions.py
"""
Riot Data Dragon에서 챔피언 전체 데이터를 가져와 DB에 저장.

사용법:
    python -m src.meta.champions          # 최신 버전으로 저장
    python -m src.meta.champions --dry-run  # DB 저장 없이 출력만
"""

import sqlite3
import asyncio
import argparse
import httpx
import json


DATA_DRAGON_VERSION_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DATA_DRAGON_CHAMPION_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/ko_KR/champion.json"


# ──────────────────────────────────────────────
# DB 테이블 생성 (없으면)
# ──────────────────────────────────────────────

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS champion_info (
        champion_id     TEXT PRIMARY KEY,   -- 'Darius', 'Caitlyn' 등 영문 키
        champion_name   TEXT NOT NULL,      -- '다리우스', '케이틀린' 등 한국어명
        title           TEXT,               -- '노ксus의 손' 등 부제
        primary_tag     TEXT,               -- 주 역할군 (Fighter / Tank / Mage / ...)
        secondary_tag   TEXT,               -- 부 역할군 (없으면 NULL)
        hp              REAL,
        hp_per_level    REAL,
        attack_damage   REAL,
        attack_speed    REAL,
        armor           REAL,
        spell_block     REAL,               -- 마법 저항력
        move_speed      REAL,
        patch_version   TEXT NOT NULL,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(champion_id, patch_version)
    );
"""

# ──────────────────────────────────────────────
# Riot 공식 태그 → 한국어 매핑
# ──────────────────────────────────────────────

TAG_KO = {
    "Fighter":   "전사",
    "Tank":      "탱커",
    "Mage":      "마법사",
    "Assassin":  "암살자",
    "Marksman":  "원거리딜러",
    "Support":   "서포터",
}


# ──────────────────────────────────────────────
# Data Dragon API 호출
# ──────────────────────────────────────────────

async def fetch_latest_version() -> str:
    """Data Dragon 최신 패치 버전 반환"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(DATA_DRAGON_VERSION_URL, timeout=10)
        resp.raise_for_status()
        versions = resp.json()
        return versions[0]  # 최신 버전이 첫 번째


async def fetch_champion_data(version: str) -> dict:
    """해당 버전의 전체 챔피언 데이터 반환"""
    url = DATA_DRAGON_CHAMPION_URL.format(version=version)
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()


# ──────────────────────────────────────────────
# 파싱
# ──────────────────────────────────────────────

def parse_champions(raw: dict, patch_version: str) -> list[dict]:
    """
    Data Dragon 응답에서 필요한 필드만 추출.
    반환: champion_info 테이블 삽입용 dict 목록
    """
    rows = []
    for champ_id, data in raw["data"].items():
        tags = data.get("tags", [])
        stats = data.get("stats", {})

        rows.append({
            "champion_id":    champ_id,
            "champion_name":  data.get("name", champ_id),
            "title":          data.get("title", ""),
            "primary_tag":    tags[0] if len(tags) > 0 else None,
            "secondary_tag":  tags[1] if len(tags) > 1 else None,
            "hp":             stats.get("hp"),
            "hp_per_level":   stats.get("hpperlevel"),
            "attack_damage":  stats.get("attackdamage"),
            "attack_speed":   stats.get("attackspeed"),
            "armor":          stats.get("armor"),
            "spell_block":    stats.get("spellblock"),
            "move_speed":     stats.get("movespeed"),
            "patch_version":  patch_version,
        })

    rows.sort(key=lambda x: x["champion_id"])
    return rows


# ──────────────────────────────────────────────
# DB 저장
# ──────────────────────────────────────────────

def save_champion_info(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """champion_info 테이블에 UPSERT. 저장된 행 수 반환."""
    conn.execute(CREATE_TABLE_SQL)

    sql = """
        INSERT INTO champion_info (
            champion_id, champion_name, title,
            primary_tag, secondary_tag,
            hp, hp_per_level, attack_damage, attack_speed,
            armor, spell_block, move_speed,
            patch_version, updated_at
        ) VALUES (
            :champion_id, :champion_name, :title,
            :primary_tag, :secondary_tag,
            :hp, :hp_per_level, :attack_damage, :attack_speed,
            :armor, :spell_block, :move_speed,
            :patch_version, CURRENT_TIMESTAMP
        )
        ON CONFLICT(champion_id, patch_version)
        DO UPDATE SET
            champion_name  = excluded.champion_name,
            title          = excluded.title,
            primary_tag    = excluded.primary_tag,
            secondary_tag  = excluded.secondary_tag,
            hp             = excluded.hp,
            hp_per_level   = excluded.hp_per_level,
            attack_damage  = excluded.attack_damage,
            attack_speed   = excluded.attack_speed,
            armor          = excluded.armor,
            spell_block    = excluded.spell_block,
            move_speed     = excluded.move_speed,
            updated_at     = CURRENT_TIMESTAMP
    """
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

async def main_async(db_path: str, dry_run: bool):
    print("[버전 확인] Data Dragon 최신 버전 조회 중...")
    version = await fetch_latest_version()
    print(f"[버전] {version}")

    print("[데이터 수집] 챔피언 전체 데이터 다운로드 중...")
    raw = await fetch_champion_data(version)

    rows = parse_champions(raw, version)
    print(f"[파싱 완료] {len(rows)}개 챔피언")

    # 역할군별 분포 출력
    from collections import Counter
    tag_counter = Counter(r["primary_tag"] for r in rows)
    print("\n[주 역할군 분포]")
    for tag, cnt in sorted(tag_counter.items(), key=lambda x: -x[1]):
        ko = TAG_KO.get(tag, tag)
        print(f"  {tag:<12} ({ko:<8}) {cnt}개")

    # 샘플 5개 출력
    print("\n[샘플 5개]")
    for r in rows[:5]:
        print(f"  {r['champion_id']:<15} {r['champion_name']:<8} "
              f"{r['primary_tag']}/{r['secondary_tag'] or '-':<12} "
              f"HP:{r['hp']} ATK:{r['attack_damage']}")

    if dry_run:
        print("\n[dry-run] DB 저장 생략")
        return

    conn = sqlite3.connect(db_path)
    saved = save_champion_info(conn, rows)
    conn.close()
    print(f"\n[저장 완료] champion_info에 {saved}개 행 UPSERT")


def main():
    parser = argparse.ArgumentParser(description="Data Dragon 챔피언 데이터 수집")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 출력만")
    parser.add_argument("--db", default="data/lol_coach.db", help="SQLite DB 경로")
    args = parser.parse_args()
    asyncio.run(main_async(args.db, args.dry_run))


if __name__ == "__main__":
    main()