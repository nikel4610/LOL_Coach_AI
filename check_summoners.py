import sqlite3
conn = sqlite3.connect('data/lol_coach.db')
conn.row_factory = sqlite3.Row

positions = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

def pick(pos, tiers):
    return conn.execute("""
        SELECT s.game_name, s.tag_line, s.tier, s.rank, COUNT(*) as games
        FROM summoners s
        JOIN match_participants mp ON s.puuid = mp.puuid
        WHERE s.tier IN ({})
          AND s.game_name IS NOT NULL AND s.game_name != ''
          AND mp.position = ?
        GROUP BY s.puuid
        ORDER BY games DESC
        LIMIT 1
    """.format(",".join("?"*len(tiers))), (*tiers, pos)).fetchone()

HIGH = ("MASTER", "GRANDMASTER", "CHALLENGER")
LOW  = ("IRON", "BRONZE", "SILVER", "GOLD")

print(f"{'포지션':<8}  {'구분':<5}  {'닉네임':<30}  {'티어'}")
print("-" * 65)
for pos in positions:
    for label, tiers in [("고티어", HIGH), ("저티어", LOW)]:
        row = pick(pos, tiers)
        if row:
            print(f"{pos:<8}  {label}  {row['game_name']}#{row['tag_line']:<25}  {row['tier']} {row['rank']}  ({row['games']}게임)")

conn.close()
