# test_validator.py
import sqlite3
from src.analysis.validator import (
    validate_analysis_input,
    SummonerNotFoundError,
    InsufficientGamesError,
    TierAverageNotFoundError,
)

conn = sqlite3.connect("data/lol_coach.db")
patch = conn.execute(
    "SELECT game_version FROM matches ORDER BY game_start_ts DESC LIMIT 1"
).fetchone()[0]

# 정상 케이스
puuid = conn.execute(
    "SELECT puuid FROM summoners WHERE tier IS NOT NULL LIMIT 1"
).fetchone()[0]
result = validate_analysis_input(conn, puuid, "GOLD", patch)
print("[정상]", result)

# 에러 케이스 1 — 존재하지 않는 puuid
try:
    validate_analysis_input(conn, "fake_puuid_1234", "GOLD", patch)
except SummonerNotFoundError as e:
    print("[에러 정상 처리] SummonerNotFoundError:", e)

# 에러 케이스 2 — 잘못된 티어
try:
    validate_analysis_input(conn, puuid, "DIAMOND5", patch)
except Exception as e:
    print("[에러 정상 처리]", type(e).__name__, e)