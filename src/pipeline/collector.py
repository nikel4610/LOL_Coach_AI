"""
데이터 수집 파이프라인 메인 모듈.

역할:
- 티어별 플레이어 목록 수집 (League API)
- 각 플레이어의 매치 히스토리 + 타임라인 수집
- storage.py로 DB 저장

사용법:
    # 전체 티어 수집 (기본값)
    python -m src.pipeline.collector

    # 특정 티어만 수집
    python -m src.pipeline.collector --tier GOLD --division I --count 10
"""

import asyncio
import argparse
from loguru import logger

from src.api.client import RiotClient
from src.api.endpoints import TIERS, DIVISIONS
from src.db.init_db import get_connection
from src.pipeline.storage import (
    upsert_summoner,
    process_and_save_match,
)


# ── 설정 ──────────────────────────────────────────────────────

# 티어당 수집할 플레이어 수 (테스트: 5명 / 본수집: 50~100명)
DEFAULT_PLAYERS_PER_TIER = 5

# 플레이어당 수집할 최근 게임 수
DEFAULT_MATCHES_PER_PLAYER = 20

# 타임라인 수집 여부 (용량 큼 — 테스트 시 False 권장)
COLLECT_TIMELINE = True


# ── 플레이어 수집 ─────────────────────────────────────────────

async def collect_players_by_tier(
    client: RiotClient,
    tier: str,
    division: str,
    max_players: int = DEFAULT_PLAYERS_PER_TIER,
) -> list[dict]:
    """
    특정 티어/디비전의 플레이어 목록 수집.
    활성 플레이어 기준: 총 게임 수(wins+losses) 30판 이상
    """
    logger.info(f"플레이어 목록 수집: {tier} {division}")
    players = await client.get_league_entries(tier, division, page=1)

    if not players:
        logger.warning(f"플레이어 없음: {tier} {division}")
        return []

    # 활성 플레이어 필터링 (게임 수 30판 이상)
    active = [
        p for p in players
        if p.get("wins", 0) + p.get("losses", 0) >= 30
    ]

    # 게임 수 많은 순으로 정렬
    active.sort(key=lambda p: p.get("wins", 0) + p.get("losses", 0), reverse=True)

    selected = active[:max_players]
    logger.info(f"  → {len(selected)}명 선택 (전체 {len(players)}명 중 활성 {len(active)}명)")
    return selected


# ── 소환사 정보 수집 ──────────────────────────────────────────

async def collect_summoner_info(
    client: RiotClient,
    conn,
    league_entry: dict,
) -> str | None:
    """
    League entry에서 puuid 조회 후 소환사 정보 저장.
    반환값: puuid (실패 시 None)
    """
    summoner_id = league_entry.get("summonerId", "")
    game_name   = league_entry.get("summonerName", "")

    # summonerName으로 Riot ID 검색이 어려우므로
    # puuid는 League entry에 포함된 경우 바로 사용
    puuid = league_entry.get("puuid")

    if not puuid:
        logger.warning(f"puuid 없음: {game_name} — 건너뜀")
        return None

    # 소환사 상세 정보 조회
    summoner = await client.get_summoner_by_puuid(puuid)

    # DB 저장
    with conn:
        upsert_summoner(
            conn,
            puuid=puuid,
            game_name=game_name,
            tag_line="KR1",          # League entry엔 태그 없음 — 기본값
            summoner=summoner,
            league=league_entry,
        )

    return puuid


# ── 매치 수집 ─────────────────────────────────────────────────

async def collect_matches_for_player(
    client: RiotClient,
    puuid: str,
    match_count: int = DEFAULT_MATCHES_PER_PLAYER,
):
    """플레이어 1명의 최근 매치 히스토리 수집 + 저장."""
    match_ids = await client.get_match_ids(puuid, count=match_count)

    if not match_ids:
        logger.warning(f"매치 없음: {puuid[:16]}...")
        return 0

    # 이미 수집한 매치 ID 제외 (중복 방지)
    conn = get_connection()
    existing = {
        row[0] for row in
        conn.execute("SELECT match_id FROM matches").fetchall()
    }
    conn.close()

    new_ids = [mid for mid in match_ids if mid not in existing]
    logger.info(f"  {puuid[:16]}... → 신규 {len(new_ids)}/{len(match_ids)}게임 수집")

    saved = 0
    for match_id in new_ids:
        match = await client.get_match(match_id)
        if not match:
            continue

        timeline = None
        if COLLECT_TIMELINE:
            timeline = await client.get_match_timeline(match_id)

        process_and_save_match(match, timeline, save_raw=True)
        saved += 1

    return saved


# ── 메인 파이프라인 ───────────────────────────────────────────

async def run_pipeline(
    tiers: list[str] = None,
    divisions: list[str] = None,
    players_per_tier: int = DEFAULT_PLAYERS_PER_TIER,
    matches_per_player: int = DEFAULT_MATCHES_PER_PLAYER,
):
    """전체 수집 파이프라인 실행."""
    tiers     = tiers     or TIERS
    divisions = divisions or ["I"]   # 기본값: 각 티어 1디비전만

    total_players = 0
    total_matches = 0

    async with RiotClient() as client:
        for tier in tiers:
            for division in divisions:
                logger.info(f"══ {tier} {division} 수집 시작 ══")

                # 1. 플레이어 목록
                players = await collect_players_by_tier(
                    client, tier, division, players_per_tier
                )
                if not players:
                    continue

                conn = get_connection()

                for i, player in enumerate(players, 1):
                    logger.info(f"  [{i}/{len(players)}] {player.get('summonerName', '?')}")

                    # 2. 소환사 정보
                    puuid = await collect_summoner_info(client, conn, player)
                    if not puuid:
                        continue

                    # 3. 매치 수집
                    saved = await collect_matches_for_player(
                        client, puuid, matches_per_player
                    )
                    total_matches += saved
                    total_players += 1

                conn.close()
                logger.info(f"  {tier} {division} 완료")

    logger.info(f"══ 수집 완료: 플레이어 {total_players}명 / 매치 {total_matches}게임 ══")


# ── CLI 진입점 ────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LoL Coach AI 데이터 수집기")
    parser.add_argument("--tier",     type=str, help="특정 티어 (예: GOLD)")
    parser.add_argument("--division", type=str, help="특정 디비전 (예: I)")
    parser.add_argument("--players",  type=int, default=DEFAULT_PLAYERS_PER_TIER,
                        help=f"티어당 수집 플레이어 수 (기본: {DEFAULT_PLAYERS_PER_TIER})")
    parser.add_argument("--matches",  type=int, default=DEFAULT_MATCHES_PER_PLAYER,
                        help=f"플레이어당 수집 게임 수 (기본: {DEFAULT_MATCHES_PER_PLAYER})")
    args = parser.parse_args()

    tiers     = [args.tier.upper()]     if args.tier     else None
    divisions = [args.division.upper()] if args.division else None

    asyncio.run(run_pipeline(
        tiers=tiers,
        divisions=divisions,
        players_per_tier=args.players,
        matches_per_player=args.matches,
    ))