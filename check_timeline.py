import sqlite3
conn = sqlite3.connect('data/lol_coach.db')

# 어떤 분 데이터가 있는지
rows = conn.execute("""
    SELECT minute, COUNT(*) as cnt
    FROM timeline_snapshots
    GROUP BY minute
    ORDER BY minute
""").fetchall()
print("=== 타임라인 분별 데이터 수 ===")
for r in rows:
    print(f"  {r[0]:>3}분  {r[1]:,}건")

# 어떤 컬럼이 있는지
cur = conn.execute("SELECT * FROM timeline_snapshots LIMIT 1")
print("\n=== 컬럼 목록 ===")
print([d[0] for d in cur.description])

conn.close()
