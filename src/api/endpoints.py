"""
Riot API 엔드포인트 상수.

라우팅 서버:
  - REGION: 매치/계정 데이터 (asia / americas / europe)
  - PLATFORM: 소환사/리그 데이터 (kr / na1 / euw1 등)
"""

# 플랫폼 (소환사/리그 관련)
PLATFORM = "https://kr.api.riotgames.com"

# 리전 (매치/계정 관련)
REGION = "https://asia.api.riotgames.com"

# ── Summoner API ──────────────────────────────────────────────
SUMMONER_BY_NAME    = PLATFORM + "/lol/summoner/v4/summoners/by-name/{summonerName}"
SUMMONER_BY_PUUID   = PLATFORM + "/lol/summoner/v4/summoners/by-puuid/{encryptedPUUID}"

# ── Account API (Riot ID 기반) ────────────────────────────────
ACCOUNT_BY_RIOT_ID  = REGION + "/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}"

# ── Match API ─────────────────────────────────────────────────
MATCH_IDS_BY_PUUID  = REGION + "/lol/match/v5/matches/by-puuid/{puuid}/ids"
MATCH_BY_ID         = REGION + "/lol/match/v5/matches/{matchId}"
MATCH_TIMELINE      = REGION + "/lol/match/v5/matches/{matchId}/timeline"

# ── League API ────────────────────────────────────────────────
LEAGUE_ENTRIES      = PLATFORM + "/lol/league/v4/entries/{queue}/{tier}/{division}"
LEAGUE_BY_SUMMONER  = PLATFORM + "/lol/league/v4/entries/by-summoner/{encryptedSummonerId}"
LEAGUE_BY_PUUID    = PLATFORM + "/lol/league/v4/entries/by-puuid/{encryptedPUUID}"

# ── Champion Mastery API ──────────────────────────────────────
MASTERY_BY_PUUID    = PLATFORM + "/lol/champion-mastery/v4/champion-masteries/by-puuid/{encryptedPUUID}"
MASTERY_TOP         = PLATFORM + "/lol/champion-mastery/v4/champion-masteries/by-puuid/{encryptedPUUID}/top"

# ── Data Dragon ───────────────────────────────────────────────
DDRAGON_VERSIONS    = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_CHAMPIONS   = "https://ddragon.leagueoflegends.com/cdn/{version}/data/ko_KR/champion.json"
DDRAGON_ITEMS       = "https://ddragon.leagueoflegends.com/cdn/{version}/data/ko_KR/item.json"
DDRAGON_CHAMPION_IMG = "https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{filename}"
DDRAGON_ITEM_IMG    = "https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{itemId}.png"

# ── 큐 타입 ───────────────────────────────────────────────────
QUEUE_RANKED_SOLO   = "RANKED_SOLO_5x5"
QUEUE_RANKED_FLEX   = "RANKED_TEAM_5x5"

QUEUE_ID_RANKED_SOLO = 420
QUEUE_ID_RANKED_FLEX = 440
QUEUE_ID_NORMAL      = 400
QUEUE_ID_ARAM        = 450

# ── 티어 목록 (수집 대상) ─────────────────────────────────────
TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND"]
DIVISIONS = ["I", "II", "III", "IV"]