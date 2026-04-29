# src/meta/role_lookup.py
"""
챔피언 역할군 조회 함수.
compare.py, coach/ 등에서 import해서 사용.
"""

import sqlite3
from functools import lru_cache


def get_champion_role(
    conn: sqlite3.Connection,
    champion_name: str,
) -> dict:
    """
    챔피언명(영문)으로 역할군 정보 조회.
    반환:
    {
        "champion_id":   str,
        "champion_name": str,   # 한국어명
        "final_role":    str,   # 최종 역할군
        "main_position": str,   # 주 포지션
        "riot_primary":  str,   # Riot 공식 태그
        "role_override": str,   # 수동 오버라이드 (없으면 None)
    }
    데이터 없으면 None 반환.
    """
    row = conn.execute(
        """
        SELECT champion_id, champion_name, final_role,
               main_position, riot_primary, role_override
        FROM champion_roles
        WHERE champion_id = ?
        """,
        (champion_name,)
    ).fetchone()

    if not row:
        return None

    return {
        "champion_id":   row[0],
        "champion_name": row[1],
        "final_role":    row[2],
        "main_position": row[3],
        "riot_primary":  row[4],
        "role_override": row[5],
    }


def get_build_type(dmg_dealt: float, dmg_taken: float) -> str:
    """
    딜량/받은피해 비율로 빌드 유형 추론.
    반환: 'damage' | 'tank' | 'fighter'
    """
    if dmg_taken == 0:
        return "damage"
    ratio = dmg_dealt / dmg_taken
    if ratio > 1.5:
        return "damage"
    if ratio < 0.8:
        return "tank"
    return "fighter"


def get_evaluation_context(
    conn: sqlite3.Connection,
    champion_name: str,
    position: str,
    dmg_dealt: float = 0,
    dmg_taken: float = 0,
) -> str:
    """
    챔피언 + 포지션 + 빌드 유형을 조합해 평가 컨텍스트 반환.

    반환 예시:
        'jungle'         정글 포지션
        'support'        서폿 포지션
        'tank'           탑/미드/봇 탱커
        'damage'         딜 빌드
        'fighter'        파이터형
        'splitpusher'    스플리터
        'engage_tank'    이니시 탱커
    """
    # 포지션 우선
    if position == "JUNGLE":
        return "jungle"
    if position == "UTILITY":
        return "support"

    role_info = get_champion_role(conn, champion_name)
    final_role = role_info["final_role"] if role_info else "Fighter"

    # 오버라이드 역할군은 빌드 무관하게 그대로 사용
    if final_role in ("splitpusher", "engage_tank", "utility_tank",
                      "poke_mage", "battlemage", "enchanter", "engage_support"):
        return final_role

    # 탱커/파이터/딜러는 실제 빌드로 구분
    build = get_build_type(dmg_dealt, dmg_taken)

    if final_role == "Tank":
        return "tank" if build != "damage" else "damage"
    if final_role in ("Fighter",):
        return build  # damage / tank / fighter
    if final_role in ("Mage", "Assassin"):
        return "damage"
    if final_role == "Marksman":
        return "damage"
    if final_role == "Support":
        return "support"

    return build