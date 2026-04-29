# test_roles.py
import sqlite3
from src.meta.role_lookup import get_champion_role, get_evaluation_context

conn = sqlite3.connect("data/lol_coach.db")

# 역할군 조회 테스트
for champ in ["Malphite", "Fiora", "Ahri", "Caitlyn", "Thresh"]:
    info = get_champion_role(conn, champ)
    if info:
        print(f"{champ:<12} → {info['final_role']:<15} (주포지션: {info['main_position']})")

print()

# 평가 컨텍스트 테스트
cases = [
    ("Malphite", "TOP",     5000,  25000),  # 탱 말파
    ("Malphite", "TOP",     25000, 5000),   # AP 말파
    ("Malphite", "JUNGLE",  10000, 10000),  # 정글 말파
    ("Fiora",    "TOP",     20000, 15000),  # 피오라
    ("Thresh",   "UTILITY", 5000,  8000),   # 쓰레쉬
]
for champ, pos, dealt, taken in cases:
    ctx = get_evaluation_context(conn, champ, pos, dealt, taken)
    print(f"{champ:<12} {pos:<8} dealt:{dealt:<6} taken:{taken:<6} → {ctx}")