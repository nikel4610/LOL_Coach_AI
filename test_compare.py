# test_compare.py
import sqlite3
import json
from src.analysis.compare import build_coach_payload

conn = sqlite3.connect("data/lol_coach.db")

# 수집된 소환사 1명
row = conn.execute(
    "SELECT puuid, tier FROM summoners WHERE tier IS NOT NULL LIMIT 1"
).fetchone()
puuid, tier = row

payload = build_coach_payload(conn, puuid, tier=tier)

print(f"[소환사] {payload['summoner']['game_name']} ({tier}) — 주 포지션: {payload['main_position']}")

print("\n[약점 TOP 3]")
for w in payload["weaknesses"]:
    print(f"  {w['label']:<15} 본인: {w['personal']:>7} | 티어평균: {w['tier_avg']:>7} | {w['diff_pct']:+.1f}%")

print("\n[강점 TOP 3]")
for s in payload["strengths"]:
    print(f"  {s['label']:<15} 본인: {s['personal']:>7} | 티어평균: {s['tier_avg']:>7} | {s['diff_pct']:+.1f}%")