"""raw 매치 JSON에서 game_name 추출해서 DB 업데이트."""
import json
import sqlite3
from pathlib import Path
from loguru import logger

conn = sqlite3.connect("data/lol_coach.db")

# 업데이트 대상 puuid 목록
target_puuids = {
    row[0] for row in conn.execute("""
        SELECT puuid FROM summoners
        WHERE game_name = '' OR game_name IS NULL
    """).fetchall()
}
logger.info(f"업데이트 대상: {len(target_puuids)}명")

updated = {}
files = sorted(Path("data/raw/matches").glob("*.json"))

for f in files:
    if not target_puuids - set(updated.keys()):
        break  # 전부 찾으면 조기 종료

    with open(f, encoding="utf-8") as fp:
        d = json.load(fp)

    for p in d.get("info", {}).get("participants", []):
        puuid = p.get("puuid")
        if puuid in target_puuids and puuid not in updated:
            game_name = p.get("riotIdGameName", "")
            tag_line  = p.get("riotIdTagline", "")
            updated[puuid] = (game_name, tag_line)

logger.info(f"매치 파일에서 {len(updated)}명 이름 추출 완료")

# DB 업데이트
for puuid, (game_name, tag_line) in updated.items():
    conn.execute("""
        UPDATE summoners SET game_name = ?, tag_line = ?
        WHERE puuid = ?
    """, (game_name, tag_line, puuid))

conn.commit()
conn.close()
logger.info("업데이트 완료")