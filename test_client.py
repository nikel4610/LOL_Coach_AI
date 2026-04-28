"""
Riot API 연결 테스트 스크립트.

사용법:
    python test_client.py "닉네임" "태그"
    예시: python test_client.py "Hide on bush" "KR1"
"""

import asyncio
import sys
from src.api.client import RiotClient


async def test(game_name: str, tag_line: str):
    print(f"\n테스트 대상: {game_name}#{tag_line}")
    print("-" * 40)

    async with RiotClient() as client:

        # 1. 계정 정보
        print("1. 계정 정보 조회...")
        account = await client.get_account_by_riot_id(game_name, tag_line)
        if not account:
            print("   계정을 찾을 수 없습니다.")
            return
        print(f"   puuid: {account['puuid'][:20]}...")
        print(f"   응답 키: {list(account.keys())}")

        # 2. 소환사 정보
        print("2. 소환사 정보 조회...")
        summoner = await client.get_summoner_by_puuid(account["puuid"])
        if not summoner:
            print("   소환사 정보를 찾을 수 없습니다.")
            return
        print(f"   응답 키: {list(summoner.keys())}")
        summoner_id = summoner.get("id") or summoner.get("summonerId", "")
        print(f"   summonerId: {summoner_id[:20]}...")

        # 3. 리그 정보 (티어)
        print("3. 리그 정보 조회...")
        # 수정
        leagues = await client.get_league_by_puuid(account["puuid"])
        if not leagues:
            print("   리그 정보 없음")
        else:
            solo = next((l for l in leagues if l["queueType"] == "RANKED_SOLO_5x5"), None)

        # 4. 최근 매치 ID
        print("4. 최근 매치 ID 조회...")
        match_ids = await client.get_match_ids(account["puuid"], count=3)
        print(f"   최근 {len(match_ids)}게임: {match_ids}")

        # 5. 매치 상세 (1게임)
        if match_ids:
            print("5. 매치 상세 조회 (1게임)...")
            match = await client.get_match(match_ids[0])
            duration = match["info"]["gameDuration"] // 60
            participants = [
                p.get("riotIdGameName", p.get("summonerName", "Unknown"))
                for p in match["info"]["participants"]
            ]
            print(f"   게임 시간: {duration}분")
            print(f"   참가자: {participants[:3]}... 등 10명")

        # 6. Data Dragon 버전
        print("6. 최신 패치 버전 확인...")
        version = await client.get_latest_version()
        print(f"   최신 버전: {version}")

        print("\n모든 테스트 통과!")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python test_client.py \"닉네임\" \"태그\"")
        print("예시:   python test_client.py \"Hide on bush\" \"KR1\"")
        sys.exit(1)

    game_name = sys.argv[1]
    tag_line = sys.argv[2]
    asyncio.run(test(game_name, tag_line))