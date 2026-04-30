"""
데이터 수집 파이프라인 메인 모듈.

역할:
- 티어별 플레이어 목록 수집 (League API)
- 각 플레이어의 매치 히스토리 + 타임라인 수집
- storage.py로 DB 저장

사용법:
    # 전체 티어 수집 (아이언~챌린저)
    python -m src.pipeline.collector

    # 특정 티어만 수집
    python -m src.pipeline.collector --tier GOLD --division I
    python -m src.pipeline.collector --tier MASTER
"""

import asyncio
import argparse
from loguru import logger

from src.api.client import RiotClient
from src.api.endpoints import TIERS, APEX_TIERS, DIVISIONS
from src.db.init_db import get_connection
from src.pipeline.storage import (
    upsert_summoner,
    process_and_save_match,
)


# ── 설정 ──────────────────────────────────────────────────────

DEFAULT_PLAYERS_PER_TIER   = 5
DEFAULT_MATCHES_PER_PLAYER = 20
COLLECT_TIMELINE           = True


# ── 일반 티어 플레이어 수집 ───────────────────────────────────

async def collect_players_by_tier(
    client: RiotClient,
    tier: str,
    division: str,
    max_players: int = DEFAULT_PLAYERS_PER_TIER,
) -> list[dict]:
    """아이언~다이아 티어/디비전별 플레이어 목록 수집."""
    logger.info(f"플레이어 목록 수집: {tier} {division}")
    players = await client.get_league_entries(tier, division, page=1)

    if not players:
        logger.warning(f"플레이어 없음: {tier} {division}")
        return []

    active = [
        p for p in players
        if p.get("wins", 0) + p.get("losses", 0) >= 30
    ]
    active.sort(key=lambda p: p.get("wins", 0) + p.get("losses", 0), reverse=True)
    selected = active[:max_players]

    logger.info(f"  → {len(selected)}명 선택 (전체 {len(players)}명 중 활성 {len(active)}명)")
    return selected


# ── 최상위 티어 플레이어 수집 (마스터/그마/챌) ───────────────

async def collect_apex_tier_players(
    client: RiotClient,
    tier: str,
    max_players: int = DEFAULT_PLAYERS_PER_TIER,
) -> list[dict]:
    """마스터/그랜드마스터/챌린저 플레이어 목록 수집."""
    logger.info(f"플레이어 목록 수집: {tier}")

    if tier == "MASTER":
        data = await client.get_master_league()
    elif tier == "GRANDMASTER":
        data = await client.get_grandmaster_league()
    elif tier == "CHALLENGER":
        data = await client.get_challenger_league()
    else:
        return []

    if not data:
        logger.warning(f"데이터 없음: {tier}")
        return []

    entries = data.get("entries", [])

    # 활성 플레이어 필터 (30판 이상)
    active = [
        e for e in entries
        if e.get("wins", 0) + e.get("losses", 0) >= 30
    ]
    active.sort(key=lambda e: e.get("wins", 0) + e.get("losses", 0), reverse=True)
    selected = active[:max_players]

    # tier/rank 필드 주입 (일반 티어 형식과 통일)
    for e in selected:
        e["tier"] = tier
        e["rank"] = "I"

    logger.info(f"  → {len(selected)}명 선택 (전체 {len(entries)}명 중 활성 {len(active)}명)")
    return selected


# ── 소환사 정보 저장 ──────────────────────────────────────────

async def collect_summoner_info(
    client: RiotClient,
    conn,
    league_entry: dict,
) -> str | None:
    """League entry에서 puuid 확인 후 소환사 정보 DB 저장."""
    puuid = league_entry.get("puuid")

    if not puuid:
        logger.warning(f"puuid 없음 — 건너뜀")
        return None

    # [수정] summonerName 대신 Account API로 game_name 조회
    account = await client.get_account_by_puuid(puuid)
    game_name = account.get("gameName", "") if account else ""
    tag_line  = account.get("tagLine", "KR1") if account else "KR1"

    summoner = await client.get_summoner_by_puuid(puuid)

    with conn:
        upsert_summoner(
            conn,
            puuid=puuid,
            game_name=game_name,
            tag_line=tag_line,
            summoner=summoner,
            league=league_entry,
        )

    return puuid


# ── 매치 수집 ─────────────────────────────────────────────────

async def collect_matches_for_player(
    client: RiotClient,
    puuid: str,
    match_count: int = DEFAULT_MATCHES_PER_PLAYER,
) -> int:
    """플레이어 1명의 최근 매치 히스토리 수집 + 저장."""
    match_ids = await client.get_match_ids(puuid, count=match_count)

    if not match_ids:
        logger.warning(f"매치 없음: {puuid[:16]}...")
        return 0

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


# ── 공통 플레이어 처리 ────────────────────────────────────────

async def process_players(
    client: RiotClient,
    players: list[dict],
    matches_per_player: int,
    total_players: int,
    total_matches: int,
) -> tuple[int, int]:
    """플레이어 목록을 받아 소환사 정보 + 매치 수집."""
    conn = get_connection()

    for i, player in enumerate(players, 1):
        logger.info(f"  [{i}/{len(players)}] {player.get('summonerName', '?')} "
                    f"({player.get('tier', '')} {player.get('rank', '')})")

        puuid = await collect_summoner_info(client, conn, player)
        if not puuid:
            continue

        saved = await collect_matches_for_player(client, puuid, matches_per_player)
        total_matches += saved
        total_players += 1

    conn.close()
    return total_players, total_matches


# ── 메인 파이프라인 ───────────────────────────────────────────

async def run_pipeline(
    tiers: list[str] = None,
    divisions: list[str] = None,
    include_apex: bool = True,
    players_per_tier: int = DEFAULT_PLAYERS_PER_TIER,
    matches_per_player: int = DEFAULT_MATCHES_PER_PLAYER,
):
    """전체 수집 파이프라인 실행 (아이언~챌린저)."""
    tiers     = tiers     or TIERS
    divisions = divisions or ["I"]

    total_players = 0
    total_matches = 0

    async with RiotClient() as client:

        # 1. 일반 티어 수집 (아이언~다이아)
        for tier in tiers:
            for division in divisions:
                logger.info(f"══ {tier} {division} 수집 시작 ══")
                players = await collect_players_by_tier(
                    client, tier, division, players_per_tier
                )
                if not players:
                    continue

                total_players, total_matches = await process_players(
                    client, players, matches_per_player,
                    total_players, total_matches,
                )
                logger.info(f"  {tier} {division} 완료")

        # 2. 최상위 티어 수집 (마스터/그마/챌)
        if include_apex:
            for apex_tier in APEX_TIERS:
                logger.info(f"══ {apex_tier} 수집 시작 ══")
                players = await collect_apex_tier_players(
                    client, apex_tier, players_per_tier
                )
                if not players:
                    continue

                total_players, total_matches = await process_players(
                    client, players, matches_per_player,
                    total_players, total_matches,
                )
                logger.info(f"  {apex_tier} 완료")

        # [추가 시작] 수집 완료 후 NULL tier 소환사 자동 정리
    logger.info("NULL tier 소환사 정리 중...")
    cleanup_conn = get_connection()
    with cleanup_conn:
        cursor = cleanup_conn.execute("DELETE FROM summoners WHERE tier IS NULL")
        logger.info(f"NULL tier 소환사 {cursor.rowcount}명 삭제 완료")
    cleanup_conn.close()
    # [추가 끝]

    logger.info(f"══ 수집 완료: 플레이어 {total_players}명 / 매치 {total_matches}게임 ══")

# ── CLI 진입점 ────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LoL Coach AI 데이터 수집기")
    parser.add_argument("--tier",       type=str,  help="특정 티어 (예: GOLD, MASTER)")
    parser.add_argument("--division",   type=str,  help="특정 디비전 (예: I) — 최상위 티어엔 불필요")
    parser.add_argument("--players",    type=int,  default=DEFAULT_PLAYERS_PER_TIER,
                        help=f"티어당 수집 플레이어 수 (기본: {DEFAULT_PLAYERS_PER_TIER})")
    parser.add_argument("--matches",    type=int,  default=DEFAULT_MATCHES_PER_PLAYER,
                        help=f"플레이어당 수집 게임 수 (기본: {DEFAULT_MATCHES_PER_PLAYER})")
    parser.add_argument("--no-apex",    action="store_true",
                        help="마스터/그마/챌 수집 제외")
    args = parser.parse_args()

    # 특정 티어 지정 시
    if args.tier:
        tier_upper = args.tier.upper()

        if tier_upper in APEX_TIERS:
            # 마스터/그마/챌 단독 수집
            async def run_apex():
                async with RiotClient() as client:
                    players = await collect_apex_tier_players(
                        client, tier_upper, args.players
                    )
                    if players:
                        await process_players(client, players, args.matches, 0, 0)
            asyncio.run(run_apex())

        else:
            # 일반 티어 단독 수집
            divisions = [args.division.upper()] if args.division else ["I"]
            asyncio.run(run_pipeline(
                tiers=[tier_upper],
                divisions=divisions,
                include_apex=False,
                players_per_tier=args.players,
                matches_per_player=args.matches,
            ))
    else:
        # 전체 수집
        asyncio.run(run_pipeline(
            players_per_tier=args.players,
            matches_per_player=args.matches,
            include_apex=not args.no_apex,
        ))