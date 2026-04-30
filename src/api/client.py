import os
import asyncio
from typing import Optional

import httpx
from dotenv import load_dotenv
from loguru import logger

from src.api.rate_limiter import RateLimiter
from src.api.endpoints import (
    ACCOUNT_BY_PUUID,
    ACCOUNT_BY_RIOT_ID,
    SUMMONER_BY_PUUID,
    MATCH_IDS_BY_PUUID,
    MATCH_BY_ID,
    MATCH_TIMELINE,
    LEAGUE_ENTRIES,
    LEAGUE_BY_SUMMONER,
    LEAGUE_BY_PUUID,
    MASTER_LEAGUE,
    GRANDMASTER_LEAGUE,
    CHALLENGER_LEAGUE,
    MASTERY_BY_PUUID,
    MASTERY_TOP,
    DDRAGON_VERSIONS,
    DDRAGON_CHAMPIONS,
    DDRAGON_ITEMS,
    QUEUE_RANKED_SOLO,
    QUEUE_ID_RANKED_SOLO,
)

load_dotenv()


class RiotClient:
    """
    Riot Games API 비동기 클라이언트.

    사용 예시:
        async with RiotClient() as client:
            account = await client.get_account_by_riot_id("닉네임", "KR1")
            matches = await client.get_match_ids(account["puuid"])
    """

    def __init__(self):
        self.api_key = os.getenv("RIOT_API_KEY")
        if not self.api_key:
            raise ValueError("RIOT_API_KEY가 .env에 없습니다.")

        self.headers = {"X-Riot-Token": self.api_key}
        self.rate_limiter = RateLimiter()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=10.0,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _get(self, url: str, params: dict = None) -> dict:
        """rate limit 적용 GET 요청. 429/5xx 에러 시 재시도."""
        await self.rate_limiter.acquire()

        for attempt in range(3):
            try:
                response = await self._client.get(url, params=params)

                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning(f"Rate limit 초과. {retry_after}초 대기...")
                    await asyncio.sleep(retry_after)

                elif response.status_code == 404:
                    logger.warning(f"404 Not Found: {url}")
                    return None

                elif response.status_code in (500, 502, 503):
                    wait = 2 ** attempt
                    logger.warning(f"서버 에러 {response.status_code}. {wait}초 후 재시도 ({attempt+1}/3)")
                    await asyncio.sleep(wait)

                else:
                    logger.error(f"API 에러 {response.status_code}: {url}")
                    response.raise_for_status()

            except httpx.TimeoutException:
                logger.warning(f"타임아웃. 재시도 ({attempt+1}/3)")
                await asyncio.sleep(2)

        logger.error(f"최대 재시도 초과: {url}")
        return None

    # ── Account API ───────────────────────────────────────────

    async def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict:
        """Riot ID로 계정 정보 조회 (puuid 포함)."""
        url = ACCOUNT_BY_RIOT_ID.format(gameName=game_name, tagLine=tag_line)
        return await self._get(url)

    async def get_account_by_puuid(self, puuid: str) -> dict:
        """puuid로 Riot 계정 정보 조회 (gameName, tagLine)."""
        url = ACCOUNT_BY_PUUID.format(puuid=puuid)
        return await self._get(url)

    async def get_summoner_by_puuid(self, puuid: str) -> dict:
        """puuid로 소환사 정보 조회."""
        url = SUMMONER_BY_PUUID.format(encryptedPUUID=puuid)
        return await self._get(url)

    # ── Match API ─────────────────────────────────────────────

    async def get_match_ids(
        self,
        puuid: str,
        count: int = 50,
        queue: int = QUEUE_ID_RANKED_SOLO,
    ) -> list[str]:
        """최근 N게임 매치 ID 목록 조회."""
        url = MATCH_IDS_BY_PUUID.format(puuid=puuid)
        result = await self._get(url, params={"count": count, "queue": queue})
        return result or []

    async def get_match(self, match_id: str) -> dict:
        """매치 상세 정보 조회."""
        url = MATCH_BY_ID.format(matchId=match_id)
        return await self._get(url)

    async def get_match_timeline(self, match_id: str) -> dict:
        """매치 타임라인 조회 (분당 골드/CS/XP)."""
        url = MATCH_TIMELINE.format(matchId=match_id)
        return await self._get(url)

    # ── League API (일반 티어) ────────────────────────────────

    async def get_league_entries(
        self,
        tier: str,
        division: str,
        queue: str = QUEUE_RANKED_SOLO,
        page: int = 1,
    ) -> list[dict]:
        """티어/디비전별 플레이어 목록 조회."""
        url = LEAGUE_ENTRIES.format(queue=queue, tier=tier, division=division)
        result = await self._get(url, params={"page": page})
        return result or []

    async def get_league_by_summoner(self, summoner_id: str) -> list[dict]:
        """소환사 ID로 리그 정보 조회."""
        url = LEAGUE_BY_SUMMONER.format(encryptedSummonerId=summoner_id)
        result = await self._get(url)
        return result or []

    async def get_league_by_puuid(self, puuid: str) -> list[dict]:
        """puuid로 리그 정보 조회."""
        url = LEAGUE_BY_PUUID.format(encryptedPUUID=puuid)
        result = await self._get(url)
        return result or []

    # ── League API (최상위 티어) ──────────────────────────────

    async def get_master_league(self, queue: str = QUEUE_RANKED_SOLO) -> dict:
        """마스터 리그 전체 조회."""
        url = MASTER_LEAGUE.format(queue=queue)
        return await self._get(url)

    async def get_grandmaster_league(self, queue: str = QUEUE_RANKED_SOLO) -> dict:
        """그랜드마스터 리그 전체 조회."""
        url = GRANDMASTER_LEAGUE.format(queue=queue)
        return await self._get(url)

    async def get_challenger_league(self, queue: str = QUEUE_RANKED_SOLO) -> dict:
        """챌린저 리그 전체 조회."""
        url = CHALLENGER_LEAGUE.format(queue=queue)
        return await self._get(url)

    # ── Champion Mastery API ──────────────────────────────────

    async def get_champion_mastery(self, puuid: str) -> list[dict]:
        """전체 챔피언 숙련도 조회."""
        url = MASTERY_BY_PUUID.format(encryptedPUUID=puuid)
        result = await self._get(url)
        return result or []

    async def get_top_champion_mastery(self, puuid: str, count: int = 10) -> list[dict]:
        """상위 N개 챔피언 숙련도 조회."""
        url = MASTERY_TOP.format(encryptedPUUID=puuid)
        result = await self._get(url, params={"count": count})
        return result or []

    # ── Data Dragon ───────────────────────────────────────────

    async def get_latest_version(self) -> str:
        """최신 게임 패치 버전 조회."""
        async with httpx.AsyncClient() as client:
            response = await client.get(DDRAGON_VERSIONS)
            versions = response.json()
            return versions[0]

    async def get_champion_data(self, version: str) -> dict:
        """챔피언 정적 데이터 조회."""
        url = DDRAGON_CHAMPIONS.format(version=version)
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json().get("data", {})

    async def get_item_data(self, version: str) -> dict:
        """아이템 정적 데이터 조회."""
        url = DDRAGON_ITEMS.format(version=version)
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json().get("data", {})