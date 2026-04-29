# test_analysis.py (프로젝트 루트에 임시 생성)
import sqlite3
from src.analysis.queries import get_full_analysis

conn = sqlite3.connect("data/lol_coach.db")

# 수집된 소환사 1명 puuid 가져오기
puuid = conn.execute(
    "SELECT puuid FROM summoners WHERE tier IS NOT NULL LIMIT 1"
).fetchone()[0]

print(f"[테스트 대상] puuid: {puuid[:20]}...")
result = get_full_analysis(conn, puuid)

for key, val in result.items():
    print(f"\n[{key}]")
    print(val if not isinstance(val, list) else val[:2])  # 리스트는 앞 2개만