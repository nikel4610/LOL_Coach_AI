import sqlite3
conn = sqlite3.connect('data/lol_coach.db')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM tier_averages')
print('tier_averages:', cur.fetchone()[0])

cur.execute('SELECT DISTINCT patch_version FROM tier_averages')
print('patches:', cur.fetchall())

cur.execute('SELECT COUNT(*) FROM match_participants WHERE position IS NOT NULL AND position != ""')
print('participants with position:', cur.fetchone()[0])

cur.execute('SELECT position, COUNT(*) FROM match_participants GROUP BY position ORDER BY COUNT(*) DESC')
print('by position:', cur.fetchall())

cur.execute('SELECT COUNT(*) FROM summoners WHERE tier IS NOT NULL AND tier != ""')
print('summoners with tier:', cur.fetchone()[0])

conn.close()
