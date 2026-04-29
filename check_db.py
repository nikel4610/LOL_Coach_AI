"""
DB 수집 현황 확인 스크립트.

사용법:
    python check_db.py
"""

import sqlite3
from src.db.init_db import get_connection


def check():
    conn = get_connection()

    print("\n" + "=" * 50)
    print("  LoL Coach AI — DB 수집 현황")
    print("=" * 50)

    # 1. 전체 요약
    total_summoners = conn.execute("SELECT COUNT(*) FROM summoners").fetchone()[0]
    total_matches   = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    total_parts     = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
    total_timeline  = conn.execute("SELECT COUNT(*) FROM timeline_snapshots").fetchone()[0]

    print(f"\n[전체 요약]")
    print(f"  소환사:        {total_summoners:,}명")
    print(f"  매치:          {total_matches:,}게임")
    print(f"  참가자 기록:   {total_parts:,}건")
    print(f"  타임라인:      {total_timeline:,}건")

    # 2. 티어별 소환사 수
    print(f"\n[티어별 소환사 수]")
    tier_order = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM",
                  "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]

    rows = conn.execute("""
        SELECT tier, COUNT(*) as cnt
        FROM summoners
        WHERE tier IS NOT NULL
        GROUP BY tier
        ORDER BY tier
    """).fetchall()

    tier_map = {row[0]: row[1] for row in rows}
    no_tier  = conn.execute(
        "SELECT COUNT(*) FROM summoners WHERE tier IS NULL"
    ).fetchone()[0]

    for tier in tier_order:
        cnt = tier_map.get(tier, 0)
        if cnt > 0:
            bar = "█" * min(cnt, 30)
            print(f"  {tier:<15} {cnt:>4}명  {bar}")

    if no_tier > 0:
        print(f"  {'(티어없음)':<15} {no_tier:>4}명  (매치 참가자로만 수집됨)")

    # 3. 티어별 매치 수
    print(f"\n[수집 대상 플레이어 기준 매치 수]")
    rows = conn.execute("""
        SELECT s.tier, COUNT(DISTINCT mp.match_id) as cnt
        FROM match_participants mp
        JOIN summoners s ON mp.puuid = s.puuid
        WHERE s.tier IS NOT NULL
        GROUP BY s.tier
        ORDER BY s.tier
    """).fetchall()

    for row in rows:
        tier, cnt = row
        bar = "█" * min(cnt // 2, 30)
        print(f"  {tier:<15} {cnt:>4}게임  {bar}")

    # 4. 최근 수집된 매치
    print(f"\n[최근 수집된 매치 5개]")
    rows = conn.execute("""
        SELECT match_id, game_version, game_duration / 60, collected_at
        FROM matches
        ORDER BY collected_at DESC
        LIMIT 5
    """).fetchall()

    for row in rows:
        match_id, version, duration, collected_at = row
        print(f"  {match_id}  패치:{version}  {duration}분  ({collected_at[:16]})")

    print("\n" + "=" * 50 + "\n")
    conn.close()


if __name__ == "__main__":
    check()