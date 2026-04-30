import sqlite3
import pandas as pd
from pathlib import Path

conn = sqlite3.connect("data/lol_coach.db")
Path("data/reports").mkdir(exist_ok=True)

tier_order = ["IRON","BRONZE","SILVER","GOLD","PLATINUM","EMERALD","DIAMOND","MASTER","GRANDMASTER","CHALLENGER"]
tier_rank  = {t: i for i, t in enumerate(tier_order)}

# ── 0. 티어별 평균 지표 피벗 ─────────────────────────────────────────────
print("\n" + "="*60)
print("0. 티어별 평균 지표 (tier_averages 피벗)")
print("="*60)

df0 = pd.read_sql("SELECT * FROM tier_averages", conn)
pivot = df0.pivot_table(
    index=["tier", "position"],
    columns="metric",
    values="avg_value"
).reset_index()
pivot["tier_rank"] = pivot["tier"].map(tier_rank)
pivot = pivot.sort_values(["tier_rank", "position"]).drop(columns="tier_rank")
pivot.columns.name = None
pd.set_option("display.float_format", "{:.2f}".format)
print(pivot.to_string(index=False))
pivot.to_csv("data/reports/00_tier_averages_pivot.csv", index=False, encoding="utf-8-sig")
print("[저장] data/reports/00_tier_averages_pivot.csv")

# ── 1. 챔피언별 포지션 분포 ──────────────────────────────────────────────
print("\n" + "="*60)
print("1. 챔피언별 포지션 분포 (픽 수 상위 30)")
print("="*60)

df1 = pd.read_sql("""
    SELECT 
        champion_name, position,
        COUNT(*) as pick_count,
        ROUND(AVG(CASE WHEN win=1 THEN 1.0 ELSE 0 END)*100, 1) as win_rate
    FROM match_participants
    WHERE position != ''
    GROUP BY champion_name, position
    ORDER BY pick_count DESC
    LIMIT 30
""", conn)
print(df1.to_string(index=False))
df1.to_csv("data/reports/01_champion_position.csv", index=False, encoding="utf-8-sig")
print("[저장] data/reports/01_champion_position.csv")

# ── 2. 티어별 소환사 수 및 평균 게임 수 ─────────────────────────────────
print("\n" + "="*60)
print("2. 티어별 소환사 수 및 평균 게임 수")
print("="*60)

df2 = pd.read_sql("""
    SELECT 
        s.tier,
        COUNT(DISTINCT s.puuid) as summoner_count,
        ROUND(AVG(g.game_count), 1) as avg_games
    FROM summoners s
    JOIN (
        SELECT puuid, COUNT(*) as game_count
        FROM match_participants
        GROUP BY puuid
    ) g ON s.puuid = g.puuid
    GROUP BY s.tier
    ORDER BY CASE s.tier
        WHEN 'IRON' THEN 1 WHEN 'BRONZE' THEN 2 WHEN 'SILVER' THEN 3
        WHEN 'GOLD' THEN 4 WHEN 'PLATINUM' THEN 5 WHEN 'EMERALD' THEN 6
        WHEN 'DIAMOND' THEN 7 WHEN 'MASTER' THEN 8 WHEN 'GRANDMASTER' THEN 9
        WHEN 'CHALLENGER' THEN 10 END
""", conn)
print(df2.to_string(index=False))
df2.to_csv("data/reports/02_summoner_summary.csv", index=False, encoding="utf-8-sig")
print("[저장] data/reports/02_summoner_summary.csv")

# ── 3. 포지션별 개인 지표 평균 ───────────────────────────────────────────
print("\n" + "="*60)
print("3. 포지션별 개인 지표 평균 (전체 참가자)")
print("="*60)

df3 = pd.read_sql("""
    SELECT
        position,
        COUNT(*) as sample,
        ROUND(AVG(kills), 1) as kills,
        ROUND(AVG(deaths), 1) as deaths,
        ROUND(AVG(assists), 1) as assists,
        ROUND(AVG(cs_per_min), 2) as cs_per_min,
        ROUND(AVG(dmg_dealt) / 60.0, 0) as dmg_per_min,
        ROUND(AVG(kp_percent), 1) as kp_pct,
        ROUND(AVG(vision_score) / 30.0, 2) as vision_per_min,
        ROUND(AVG(CASE WHEN win=1 THEN 1.0 ELSE 0 END)*100, 1) as win_rate
    FROM match_participants
    WHERE position != ''
    GROUP BY position
    ORDER BY position
""", conn)
print(df3.to_string(index=False))
df3.to_csv("data/reports/03_position_stats.csv", index=False, encoding="utf-8-sig")
print("[저장] data/reports/03_position_stats.csv")

# ── 4. 10분 스냅샷 티어별 평균 ──────────────────────────────────────────
print("\n" + "="*60)
print("4. 10분 스냅샷 티어별 평균 (cs / 골드 / xp)")
print("="*60)

df4 = pd.read_sql("""
    SELECT
        s.tier,
        ROUND(AVG(t.cs), 1) as cs_at_10,
        ROUND(AVG(t.gold), 0) as gold_at_10,
        ROUND(AVG(t.xp), 0) as xp_at_10,
        ROUND(AVG(t.cs_diff), 1) as cs_diff,
        ROUND(AVG(t.gold_diff), 0) as gold_diff,
        COUNT(*) as sample
    FROM timeline_snapshots t
    JOIN match_participants mp
        ON t.match_id = mp.match_id AND t.puuid = mp.puuid
    JOIN summoners s ON mp.puuid = s.puuid
    WHERE t.minute = 10
    GROUP BY s.tier
    ORDER BY CASE s.tier
        WHEN 'IRON' THEN 1 WHEN 'BRONZE' THEN 2 WHEN 'SILVER' THEN 3
        WHEN 'GOLD' THEN 4 WHEN 'PLATINUM' THEN 5 WHEN 'EMERALD' THEN 6
        WHEN 'DIAMOND' THEN 7 WHEN 'MASTER' THEN 8 WHEN 'GRANDMASTER' THEN 9
        WHEN 'CHALLENGER' THEN 10 END
""", conn)
print(df4.to_string(index=False))
df4.to_csv("data/reports/04_timeline_snapshot.csv", index=False, encoding="utf-8-sig")
print("[저장] data/reports/04_timeline_snapshot.csv")

conn.close()
print("\n모든 리포트 저장 완료 → data/reports/")