#!/usr/bin/env python3
"""
compare.py 동작 확인용 테스트 스크립트.

사용법:
    python test_compare.py                          # DB 상위 소환사 5명 자동 테스트
    python test_compare.py --name "Juhana"          # 특정 닉네임
    python test_compare.py --name "Juhana" --tier GOLD  # 다른 티어 기준으로 비교
    python test_compare.py --db path/to/lol_coach.db    # DB 경로 직접 지정
"""

import sqlite3
import argparse
import sys

sys.path.insert(0, ".")  # 프로젝트 루트에서 실행 가정

from src.analysis.compare import build_coach_payload


def print_payload(payload: dict):
    s = payload["summoner"]
    print(f"\n{'='*60}")
    print(f"  소환사  : {s['game_name']}#{s['tag_line']}")
    print(f"  티어    : {s['tier']} {s['rank']}  ({payload['games_analyzed']}게임 분석)")
    print(f"  포지션  : {payload['main_position']}")
    print(f"  패치    : {payload['patch']}")
    if payload["warnings"]:
        for w in payload["warnings"]:
            print(f"  ⚠  {w}")
    if payload["low_sample"]:
        print(f"  ⚠  샘플 부족 — 신뢰도 낮음")
    print(f"{'='*60}")

    print("\n[비교 결과]")
    print(f"  {'':6} {'':2} {'지표':<12} {'개인':>8}  {'티어평균':>8}  {'차이':>10}")
    print(f"  {'-'*55}")
    for r in payload["comparison"]:
        primary = "[핵심]" if r["is_primary"] else "      "
        arrow   = "▲" if r["above_avg"] else "▼"
        if r["diff_pct"] is not None:
            diff_str = f"{r['diff_pct']:>+7.1f}%"
        else:
            diff_str = f"diff {r['diff']:>+7.1f} "
        print(f"  {primary} {arrow} {r['label']:<12} {r['personal']:>8}  {r['tier_avg']:>8}  {diff_str}")

    print("\n[약점 TOP3]")
    if payload["weaknesses"]:
        for r in payload["weaknesses"]:
            pct = f"{r['diff_pct']:+.1f}%" if r["diff_pct"] is not None else f"diff {r['diff']:+.1f}"
            print(f"  ▼ {r['label']}: {r['personal']} (평균 {r['tier_avg']}, {pct})")
    else:
        print("  (약점 없음 — 모든 핵심 지표가 평균 이상)")

    print("\n[강점 TOP3]")
    if payload["strengths"]:
        for r in payload["strengths"]:
            pct = f"{r['diff_pct']:+.1f}%" if r["diff_pct"] is not None else f"diff {r['diff']:+.1f}"
            print(f"  ▲ {r['label']}: {r['personal']} (평균 {r['tier_avg']}, {pct})")
    else:
        print("  (강점 없음 — 모든 핵심 지표가 평균 미만)")
    print()


def main():
    parser = argparse.ArgumentParser(description="compare.py 테스트")
    parser.add_argument("--db",   default="data/lol_coach.db", help="DB 경로")
    parser.add_argument("--name", default=None,                help="소환사 닉네임")
    parser.add_argument("--tier", default=None,                help="비교 기준 티어 (기본: 소환사 실제 티어)")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    if args.name:
        row = conn.execute(
            "SELECT puuid, tier FROM summoners WHERE game_name = ?", (args.name,)
        ).fetchone()
        if not row:
            print(f"[오류] '{args.name}' 소환사를 DB에서 찾을 수 없습니다.")
            sys.exit(1)
        candidates = [(row["puuid"], args.tier or row["tier"])]
    else:
        # 게임 수 많은 소환사 5명 자동 선택
        rows = conn.execute("""
            SELECT s.puuid, s.game_name, s.tier, COUNT(*) AS games
            FROM summoners s
            JOIN match_participants mp ON s.puuid = mp.puuid
            WHERE s.tier IS NOT NULL AND s.game_name IS NOT NULL AND s.game_name != ''
            GROUP BY s.puuid
            ORDER BY games DESC
            LIMIT 5
        """).fetchall()
        if not rows:
            print("[오류] DB에 소환사 데이터가 없습니다.")
            sys.exit(1)
        candidates = [(r["puuid"], args.tier or r["tier"]) for r in rows]
        print(f"자동 선택된 소환사 {len(candidates)}명 테스트")

    for puuid, tier in candidates:
        try:
            payload = build_coach_payload(conn, puuid, tier=tier)
            print_payload(payload)
        except Exception as e:
            name = conn.execute(
                "SELECT game_name FROM summoners WHERE puuid=?", (puuid,)
            ).fetchone()
            print(f"\n[실패] {name[0] if name else puuid[:16]}: {e}")

    conn.close()


if __name__ == "__main__":
    main()