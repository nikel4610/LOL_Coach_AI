import sqlite3
from src.coach.prompt_builder import build_user_message
from src.analysis.compare import build_coach_payload

conn = sqlite3.connect('data/lol_coach.db')
conn.row_factory = sqlite3.Row

row = conn.execute("""
    SELECT s.puuid, s.tier FROM summoners s
    JOIN match_participants mp ON s.puuid = mp.puuid
    WHERE s.tier IS NOT NULL AND s.game_name IS NOT NULL AND s.game_name != ''
    GROUP BY s.puuid ORDER BY COUNT(*) DESC LIMIT 1
""").fetchone()

payload = build_coach_payload(conn, row['puuid'], tier=row['tier'])
msg = build_user_message(payload)
print(msg)
print("\n--- weaknesses ---")
for r in payload['weaknesses']:
    print(r)
conn.close()
