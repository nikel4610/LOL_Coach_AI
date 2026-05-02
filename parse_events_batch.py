"""
data/raw/timelines/ 전체 → match_events / match_player_teams 배치 저장.

사용법:
    python parse_events_batch.py
    python parse_events_batch.py --reset   # 기존 데이터 삭제 후 재처리
"""

import argparse
from pathlib import Path
from src.db.init_db import get_connection
from src.pipeline.event_store import parse_timeline_events, save_events

TIMELINE_DIR = Path("data/raw/timelines")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="기존 이벤트 전부 삭제 후 재처리")
    args = parser.parse_args()

    conn = get_connection()

    if args.reset:
        conn.execute("DELETE FROM match_events")
        conn.execute("DELETE FROM match_player_teams")
        conn.commit()
        print("[reset] match_events / match_player_teams 전체 삭제")

    done = {row[0] for row in conn.execute("SELECT DISTINCT match_id FROM match_player_teams").fetchall()}
    files = sorted(TIMELINE_DIR.glob("*.json"))
    todo  = [f for f in files if f.stem not in done]

    print(f"전체 타임라인: {len(files)}개 | 처리됨: {len(done)}개 | 처리 예정: {len(todo)}개")
    if not todo:
        print("모두 처리됨.")
        conn.close()
        return

    total_events = 0
    for i, f in enumerate(todo, 1):
        match_id = f.stem
        events, teams = parse_timeline_events(match_id)
        if events or teams:
            with conn:
                save_events(conn, events, teams)
            total_events += len(events)

        if i % 200 == 0 or i == len(todo):
            print(f"  [{i:>4}/{len(todo)}]  누적 이벤트 {total_events:,}건")

    conn.close()
    print(f"\n완료: {len(todo)}개 파일 / 이벤트 {total_events:,}건 저장")


if __name__ == "__main__":
    main()
