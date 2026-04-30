from src.analysis.event_parser import parse_all_timelines, get_phase_summary
import json

all_phases = parse_all_timelines()

print(f"\n총 파싱 게임 수: {len(all_phases)}")

first_bloods = [p.first_blood_ms for p in all_phases.values() if p.first_blood_ms]
first_dragons = [p.first_dragon_kill_ms for p in all_phases.values() if p.first_dragon_kill_ms]

print(f"퍼블 있는 게임: {len(first_bloods)}/{len(all_phases)}")
print(f"퍼블 평균: {sum(first_bloods)/len(first_bloods)/60000:.1f}분")
print(f"첫 드래곤 킬 평균: {sum(first_dragons)/len(first_dragons)/60000:.1f}분")