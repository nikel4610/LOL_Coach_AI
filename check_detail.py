import sqlite3
conn = sqlite3.connect('data/lol_coach.db')

print('=== 티어×포지션 샘플 수 (cs_per_min 기준) ===')
rows = conn.execute("""
    SELECT tier, position, sample_count
    FROM tier_averages
    WHERE metric = 'cs_per_min'
    ORDER BY CASE tier
        WHEN 'IRON' THEN 1 WHEN 'BRONZE' THEN 2 WHEN 'SILVER' THEN 3
        WHEN 'GOLD' THEN 4 WHEN 'PLATINUM' THEN 5 WHEN 'EMERALD' THEN 6
        WHEN 'DIAMOND' THEN 7 WHEN 'MASTER' THEN 8 WHEN 'GRANDMASTER' THEN 9
        WHEN 'CHALLENGER' THEN 10 END, position
""").fetchall()
for r in rows:
    print(f'  {r[0]:<12} {r[1]:<8} n={r[2]}')

print()
print('=== 패치별 매치 수 ===')
rows = conn.execute("""
    SELECT game_version, COUNT(*) as cnt
    FROM matches
    GROUP BY game_version
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    print(f'  {r[0]:<25} {r[1]}게임')

print()
print('=== 티어별 매치 수 (summoners 기준) ===')
rows = conn.execute("""
    SELECT s.tier, COUNT(DISTINCT mp.match_id) as matches
    FROM match_participants mp
    JOIN summoners s ON mp.puuid = s.puuid
    WHERE s.tier IS NOT NULL
    GROUP BY s.tier
    ORDER BY CASE s.tier
        WHEN 'IRON' THEN 1 WHEN 'BRONZE' THEN 2 WHEN 'SILVER' THEN 3
        WHEN 'GOLD' THEN 4 WHEN 'PLATINUM' THEN 5 WHEN 'EMERALD' THEN 6
        WHEN 'DIAMOND' THEN 7 WHEN 'MASTER' THEN 8 WHEN 'GRANDMASTER' THEN 9
        WHEN 'CHALLENGER' THEN 10 END
""").fetchall()
for r in rows:
    print(f'  {r[0]:<12} {r[1]}게임')

conn.close()
