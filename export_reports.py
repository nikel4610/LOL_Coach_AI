"""
분석 설정 / 티어 평균 / 수집 데이터 요약 → CSV 저장.

출력:
    data/reports/01_prompt_metrics.csv   포지션별 지표 설정
    data/reports/02_tier_averages.csv    티어 × 포지션 × 지표 피벗
    data/reports/03_collected_summary.csv 수집 데이터 요약
"""

import sqlite3
import csv
from pathlib import Path
from src.analysis.compare import POSITION_PROFILES, METRIC_META, _DEFAULT_PROFILE

DB_PATH   = Path("data/lol_coach.db")
OUT_DIR   = Path("data/overview")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TIER_ORDER = ["IRON","BRONZE","SILVER","GOLD","PLATINUM",
              "EMERALD","DIAMOND","MASTER","GRANDMASTER","CHALLENGER"]
POS_ORDER  = ["TOP","JUNGLE","MIDDLE","BOTTOM","UTILITY"]

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row


# ── 1. 포지션별 지표 설정 ──────────────���──────────────────────
out1 = OUT_DIR / "01_prompt_metrics.csv"
rows1 = []
all_metrics = list(METRIC_META.keys())

for metric in all_metrics:
    label, unit, higher = METRIC_META[metric]
    row = {"metric": metric, "label": label, "unit": unit, "higher_is_better": higher}
    for pos in POS_ORDER:
        profile = POSITION_PROFILES.get(pos, _DEFAULT_PROFILE)
        if metric in profile["primary"]:
            row[pos] = "primary"
        elif metric in profile.get("exclude", []):
            row[pos] = "exclude"
        else:
            row[pos] = "secondary"
    rows1.append(row)

with open(out1, "w", newline="", encoding="utf-8-sig") as f:
    cols = ["metric", "label", "unit", "higher_is_better"] + POS_ORDER
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows1)

print(f"[1] {out1}  ({len(rows1)}개 지표)")


# ── 2. 티어 평균 피벗 ──────────���──────────────────────────────
out2 = OUT_DIR / "02_tier_averages.csv"

patch = conn.execute(
    "SELECT patch_version FROM tier_averages ORDER BY updated_at DESC LIMIT 1"
).fetchone()[0]

avg_rows = conn.execute(
    "SELECT tier, position, metric, avg_value, sample_count "
    "FROM tier_averages WHERE patch_version = ?",
    (patch,)
).fetchall()

# (tier, position) → {metric: value}
data2: dict[tuple, dict] = {}
samples: dict[tuple, int] = {}
for r in avg_rows:
    key = (r["tier"], r["position"])
    data2.setdefault(key, {})[r["metric"]] = r["avg_value"]
    samples[key] = r["sample_count"]

metrics_in_db = sorted({r["metric"] for r in avg_rows})

with open(out2, "w", newline="", encoding="utf-8-sig") as f:
    cols = ["tier", "position", "sample_count"] + metrics_in_db
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for tier in TIER_ORDER:
        for pos in POS_ORDER:
            key = (tier, pos)
            if key not in data2:
                continue
            row = {"tier": tier, "position": pos, "sample_count": samples.get(key, "")}
            row.update(data2[key])
            w.writerow(row)

print(f"[2] {out2}  (패치 {patch}, {len(data2)}개 티어×포지션 조합)")


# ── 3. 수집 데이터 요약 ───────────────────────────────��───────
out3 = OUT_DIR / "03_collected_summary.csv"

summary_rows = conn.execute("""
    SELECT
        s.tier,
        mp.position,
        COUNT(*)                                                    AS games,
        COUNT(DISTINCT s.puuid)                                     AS players,
        ROUND(AVG(mp.win)*100, 1)                                   AS win_rate,
        ROUND(AVG(mp.cs_per_min), 2)                                AS avg_cs_per_min,
        ROUND(AVG(mp.kp_percent), 1)                                AS avg_kp_percent,
        ROUND(AVG(mp.vision_score), 1)                              AS avg_vision_score,
        ROUND(AVG((mp.kills+mp.assists)/MAX(CAST(mp.deaths AS REAL),1.0)),2) AS avg_kda,
        ROUND(AVG(mp.dmg_dealt), 0)                                 AS avg_dmg_dealt,
        ROUND(AVG(mp.wards_placed), 1)                              AS avg_wards_placed,
        ROUND(AVG(mp.wards_killed), 1)                              AS avg_wards_killed,
        ROUND(AVG(m.game_duration)/60.0, 1)                         AS avg_game_min
    FROM match_participants mp
    JOIN summoners s   ON mp.puuid    = s.puuid
    JOIN matches   m   ON mp.match_id = m.match_id
    WHERE s.tier IS NOT NULL
      AND mp.position IS NOT NULL AND mp.position != ''
    GROUP BY s.tier, mp.position
    ORDER BY
        CASE s.tier
            WHEN 'IRON'        THEN 1 WHEN 'BRONZE'      THEN 2
            WHEN 'SILVER'      THEN 3 WHEN 'GOLD'         THEN 4
            WHEN 'PLATINUM'    THEN 5 WHEN 'EMERALD'      THEN 6
            WHEN 'DIAMOND'     THEN 7 WHEN 'MASTER'       THEN 8
            WHEN 'GRANDMASTER' THEN 9 WHEN 'CHALLENGER'   THEN 10
        END,
        CASE mp.position
            WHEN 'TOP'     THEN 1 WHEN 'JUNGLE'  THEN 2
            WHEN 'MIDDLE'  THEN 3 WHEN 'BOTTOM'  THEN 4
            WHEN 'UTILITY' THEN 5
        END
""").fetchall()

with open(out3, "w", newline="", encoding="utf-8-sig") as f:
    cols = [d[0] for d in conn.execute(
        "SELECT * FROM match_participants LIMIT 0"
    ).description]  # 컬럼명 참고용이 아니라 summary_rows에서 직접 추출
    cols = list(summary_rows[0].keys()) if summary_rows else []
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows([dict(r) for r in summary_rows])

total_games   = sum(r["games"]   for r in summary_rows)
total_players = conn.execute("SELECT COUNT(DISTINCT puuid) FROM summoners WHERE tier IS NOT NULL").fetchone()[0]
print(f"[3] {out3}  ({len(summary_rows)}개 조합, 총 {total_games:,}게임, 플레이어 {total_players:,}명)")

conn.close()
print("\n완료.")
