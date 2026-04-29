# src/analysis/tier_stats.py
"""
티어별 평균 지표 계산 후 tier_averages 테이블에 저장.

사용법:
    python -m src.analysis.tier_stats          # 전체 티어 집계
    python -m src.analysis.tier_stats --dry-run  # DB 저장 없이 출력만
"""

import sqlite3
import argparse
from datetime import datetime

# ──────────────────────────────────────────────
# 집계 대상 지표 정의
# metric 이름은 tier_averages.metric 컬럼에 그대로 저장됨
# ──────────────────────────────────────────────
METRICS = [
    "cs_per_min",
    "kp_percent",
    "vision_score",
    "vision_per_min",   # vision_score / (game_duration / 60)
    "kda",              # (kills + assists) / MAX(deaths, 1)
    "dmg_dealt",
    "dmg_share",        # 팀 내 딜 비중 (%)
    "win_rate",
    "wards_placed",
    "wards_killed",
    "gold_diff_10",     # 10분 골드차
    "cs_diff_10",       # 10분 CS차
]


def compute_tier_averages(
    conn: sqlite3.Connection,
    patch_version: str
) -> list[dict]:
    """
    수집된 소환사(tier IS NOT NULL) 기준으로
    티어 × 포지션 × metric 평균을 계산해 dict 목록 반환.
    """
    results = []

    # ── 기본 지표 (match_participants 기반) ──────────
    sql_basic = """
        SELECT
            s.tier,
            mp.position,
            COUNT(*)                                                AS sample,
            ROUND(AVG(mp.cs_per_min), 3)                           AS cs_per_min,
            ROUND(AVG(mp.kp_percent), 3)                           AS kp_percent,
            ROUND(AVG(mp.vision_score), 3)                         AS vision_score,
            ROUND(AVG(CAST(mp.vision_score AS REAL)
                  / (m.game_duration / 60.0)), 3)                  AS vision_per_min,
            ROUND(AVG(
                (mp.kills + mp.assists)
                / MAX(CAST(mp.deaths AS REAL), 1.0)
            ), 3)                                                   AS kda,
            ROUND(AVG(mp.dmg_dealt), 1)                            AS dmg_dealt,
            ROUND(AVG(mp.win) * 100, 3)                            AS win_rate,
            ROUND(AVG(mp.wards_placed), 3)                         AS wards_placed,
            ROUND(AVG(mp.wards_killed), 3)                         AS wards_killed
        FROM match_participants mp
        JOIN summoners s ON mp.puuid = s.puuid
        JOIN matches   m ON mp.match_id = m.match_id
        WHERE s.tier IS NOT NULL
          AND mp.position IS NOT NULL
          AND mp.position != ''
        GROUP BY s.tier, mp.position
        HAVING COUNT(*) >= 3
    """

    # ── dmg_share (팀 딜 비중) ──────────────────────
    sql_dmg_share = """
        WITH team_dmg AS (
            SELECT
                mp.match_id,
                mp.puuid,
                mp.win,
                mp.dmg_dealt,
                SUM(t.dmg_dealt) AS team_total_dmg
            FROM match_participants mp
            JOIN summoners s ON mp.puuid = s.puuid
            JOIN match_participants t
              ON mp.match_id = t.match_id AND mp.win = t.win
            WHERE s.tier IS NOT NULL
            GROUP BY mp.match_id, mp.puuid
        )
        SELECT
            s.tier,
            mp.position,
            ROUND(AVG(
                CAST(td.dmg_dealt AS REAL) / td.team_total_dmg * 100
            ), 3)               AS dmg_share
        FROM team_dmg td
        JOIN match_participants mp ON td.puuid = mp.puuid
                                   AND td.match_id = mp.match_id
        JOIN summoners s ON td.puuid = s.puuid
        WHERE s.tier IS NOT NULL
          AND mp.position IS NOT NULL
        GROUP BY s.tier, mp.position
    """

    # ── 10분 라인전 지표 (timeline_snapshots 기반) ──
    sql_laning = """
        SELECT
            s.tier,
            mp.position,
            ROUND(AVG(ts.gold_diff), 1)     AS gold_diff_10,
            ROUND(AVG(ts.cs_diff), 3)       AS cs_diff_10
        FROM timeline_snapshots ts
        JOIN match_participants mp
          ON ts.match_id = mp.match_id AND ts.puuid = mp.puuid
        JOIN summoners s ON ts.puuid = s.puuid
        WHERE ts.minute = 10
          AND s.tier IS NOT NULL
          AND mp.position IS NOT NULL
        GROUP BY s.tier, mp.position
        HAVING COUNT(*) >= 3
    """

    # ── 쿼리 실행 및 결과 병합 ─────────────────────
    basic_rows = {
        (r["tier"], r["position"]): r
        for r in _rows_to_dicts(conn.execute(sql_basic))
    }
    dmg_share_rows = {
        (r["tier"], r["position"]): r["dmg_share"]
        for r in _rows_to_dicts(conn.execute(sql_dmg_share))
    }
    laning_rows = {
        (r["tier"], r["position"]): r
        for r in _rows_to_dicts(conn.execute(sql_laning))
    }

    # ── dict → tier_averages 행 목록으로 변환 ──────
    basic_metrics = [
        "cs_per_min", "kp_percent", "vision_score", "vision_per_min",
        "kda", "dmg_dealt", "win_rate", "wards_placed", "wards_killed"
    ]

    for (tier, position), row in basic_rows.items():
        sample = row["sample"]
        key = (tier, position)

        # 기본 지표
        for metric in basic_metrics:
            results.append({
                "tier": tier,
                "position": position,
                "metric": metric,
                "avg_value": row[metric],
                "sample_count": sample,
                "patch_version": patch_version,
            })

        # dmg_share
        if key in dmg_share_rows:
            results.append({
                "tier": tier,
                "position": position,
                "metric": "dmg_share",
                "avg_value": dmg_share_rows[key],
                "sample_count": sample,
                "patch_version": patch_version,
            })

        # laning
        if key in laning_rows:
            for metric in ("gold_diff_10", "cs_diff_10"):
                results.append({
                    "tier": tier,
                    "position": position,
                    "metric": metric,
                    "avg_value": laning_rows[key][metric],
                    "sample_count": sample,
                    "patch_version": patch_version,
                })

    return results


def save_tier_averages(
    conn: sqlite3.Connection,
    rows: list[dict]
) -> int:
    """
    tier_averages 테이블에 UPSERT.
    같은 (tier, position, metric, patch_version)이면 덮어씀.
    저장된 행 수 반환.
    """
    sql = """
        INSERT INTO tier_averages
            (tier, position, metric, avg_value, sample_count, patch_version, updated_at)
        VALUES
            (:tier, :position, :metric, :avg_value, :sample_count, :patch_version,
             CURRENT_TIMESTAMP)
        ON CONFLICT(tier, position, metric, patch_version)
        DO UPDATE SET
            avg_value    = excluded.avg_value,
            sample_count = excluded.sample_count,
            updated_at   = CURRENT_TIMESTAMP
    """
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def get_latest_patch(conn: sqlite3.Connection) -> str:
    """DB에 수집된 가장 최신 패치 버전 반환"""
    row = conn.execute(
        "SELECT game_version FROM matches ORDER BY game_start_ts DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else "unknown"


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="티어 평균 지표 집계 및 저장")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="DB 저장 없이 집계 결과만 출력"
    )
    parser.add_argument(
        "--db", default="data/lol_coach.db",
        help="SQLite DB 경로 (기본: data/lol_coach.db)"
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    patch = get_latest_patch(conn)
    print(f"[패치 버전] {patch}")
    print("[집계 시작] 티어 × 포지션 × 지표 계산 중...")

    rows = compute_tier_averages(conn, patch)
    print(f"[집계 완료] {len(rows)}개 행 생성")

    # 결과 미리보기 (티어별 요약)
    from collections import defaultdict
    summary = defaultdict(lambda: defaultdict(int))
    for r in rows:
        summary[r["tier"]][r["position"]] += 1

    print("\n[티어 × 포지션별 지표 수]")
    for tier in ["IRON","BRONZE","SILVER","GOLD","PLATINUM",
                 "EMERALD","DIAMOND","MASTER","GRANDMASTER","CHALLENGER"]:
        if tier in summary:
            positions = ", ".join(
                f"{pos}:{cnt}" for pos, cnt in sorted(summary[tier].items())
            )
            print(f"  {tier:<15} {positions}")

    if args.dry_run:
        print("\n[dry-run] DB 저장 생략")
        return

    saved = save_tier_averages(conn, rows)
    print(f"\n[저장 완료] tier_averages에 {saved}개 행 UPSERT")
    conn.close()


if __name__ == "__main__":
    main()