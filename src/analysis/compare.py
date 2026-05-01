# src/analysis/compare.py
"""
개인 지표 vs 티어 평균 비교 + Claude API 입력용 JSON 구조화.

사용 예:
    from src.analysis.compare import build_coach_payload
    payload = build_coach_payload(conn, puuid, tier="GOLD", patch="16.8.766.8562")
"""

import sqlite3
from typing import Optional
from src.analysis.queries import get_full_analysis
from src.analysis.validator import validate_analysis_input


# ──────────────────────────────────────────────
# 포지션별 지표 프로필
# primary  : 약점/강점 판정 대상 지표
# exclude  : 비교 결과에는 포함하되 약점/강점 판정에서 제외
# ──────────────────────────────────────────────

POSITION_PROFILES = {
    "TOP": {
        "primary": [
            "cs_per_min",
            "kda", "dmg_dealt", "dmg_share", "dmg_taken",
        ],
        # cs_diff_10, gold_diff_10: 티어 평균 비교 불가 (상대 티어 편차 노이즈) → 참고 표시만
        "exclude": ["kp_percent", "cs_diff_10", "gold_diff_10"],
    },
    "MIDDLE": {
        "primary": [
            "cs_per_min",
            "kda", "dmg_dealt", "dmg_share", "kp_percent",
        ],
        "exclude": ["cs_diff_10", "gold_diff_10"],
    },
    "BOTTOM": {
        "primary": [
            "cs_per_min",
            "kda", "dmg_dealt", "dmg_share", "dmg_taken",
        ],
        "exclude": ["kp_percent", "cs_diff_10", "gold_diff_10"],
    },
    "JUNGLE": {
        "primary": [
            "kp_percent", "cs_per_min",
            "vision_score", "vision_per_min", "wards_killed",
            "kda",
        ],
        # cs_diff_10, gold_diff_10: 라이너 기준 지표 + 티어 비교 불가 이중으로 무의미
        "exclude": ["cs_diff_10", "gold_diff_10"],
    },
    "UTILITY": {
        "primary": [
            "vision_score", "vision_per_min",
            "wards_placed", "wards_killed",
            "kp_percent", "dmg_taken",
        ],
        "exclude": ["cs_per_min", "cs_diff_10", "gold_diff_10", "dmg_dealt", "dmg_share"],
    },
}

# 알 수 없는 포지션 폴백 (primary만, exclude 없음)
_DEFAULT_PROFILE = {
    "primary": [
        "cs_per_min", "kda", "kp_percent",
        "vision_score", "dmg_dealt", "dmg_share",
    ],
    "exclude": [],
}


# ──────────────────────────────────────────────
# 지표 메타 (한국어 표시명 / 단위 / 높을수록 좋은지)
# ──────────────────────────────────────────────

METRIC_META = {
    "cs_per_min":    ("분당 CS",       "개/분", True),
    "kp_percent":    ("킬 관여율",     "%",     True),
    "vision_score":  ("시야 점수",     "점",    True),
    "vision_per_min":("분당 시야",     "점/분", True),
    "kda":           ("KDA",          "",      True),
    "dmg_dealt":     ("평균 딜량",     "",      True),
    "dmg_share":     ("팀 내 딜 비중", "%",     True),
    "dmg_taken":     ("받은 피해",     "",      False),  # 낮을수록 좋음
    "win_rate":      ("승률",          "%",     True),
    "wards_placed":  ("와드 설치",     "개",    True),
    "wards_killed":  ("와드 제거",     "개",    True),
    "gold_diff_10":  ("10분 골드차",   "",      True),
    "cs_diff_10":    ("10분 CS차",     "개",    True),
}


# ──────────────────────────────────────────────
# 티어 평균 로드
# ──────────────────────────────────────────────

def get_latest_tier_patch(conn: sqlite3.Connection) -> str:
    """tier_averages에 저장된 가장 최신 패치 버전 반환."""
    row = conn.execute(
        "SELECT patch_version FROM tier_averages ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else "unknown"


def get_tier_averages(
    conn: sqlite3.Connection,
    tier: str,
    position: str,
    patch_version: str,
) -> dict[str, float]:
    """
    tier_averages에서 특정 티어/포지션/패치의 전체 지표를 {metric: avg_value}로 반환.
    해당 포지션 데이터 없으면 같은 티어 전 포지션 평균으로 폴백.
    """
    sql = """
        SELECT metric, avg_value
        FROM tier_averages
        WHERE tier = ? AND position = ? AND patch_version = ?
    """
    rows = conn.execute(sql, (tier, position, patch_version)).fetchall()

    if not rows:
        # 포지션 데이터 없음 → 같은 티어 전 포지션 평균으로 폴백
        sql_fallback = """
            SELECT metric, ROUND(AVG(avg_value), 3) AS avg_value
            FROM tier_averages
            WHERE tier = ? AND patch_version = ?
            GROUP BY metric
        """
        rows = conn.execute(sql_fallback, (tier, patch_version)).fetchall()

    return {row[0]: row[1] for row in rows}


# ──────────────────────────────────────────────
# 개인 지표 flat dict 변환
# ──────────────────────────────────────────────

def _flatten_personal(analysis: dict, position: str) -> dict[str, float]:
    """get_full_analysis 결과에서 비교 대상 지표만 추출해 flat dict 반환."""
    overall = analysis.get("overall", {})
    vision  = analysis.get("vision", {})
    damage  = analysis.get("damage", {})
    laning  = analysis.get("laning", {})

    pos_row = next(
        (r for r in analysis.get("positions", []) if r["position"] == position),
        {}
    )

    flat = {
        "cs_per_min":    pos_row.get("avg_cs_per_min")   or overall.get("avg_cs_per_min"),
        "kp_percent":    pos_row.get("avg_kp_percent")   or overall.get("avg_kp_percent"),
        "vision_score":  pos_row.get("avg_vision_score") or overall.get("avg_vision_score"),
        "vision_per_min":vision.get("vision_per_min"),
        "kda":           overall.get("kda"),
        "dmg_dealt":     pos_row.get("avg_dmg_dealt")    or overall.get("avg_dmg_dealt"),
        "dmg_taken":     damage.get("avg_dmg_taken"),
        "dmg_share":     damage.get("avg_dmg_share"),
        "win_rate":      overall.get("win_rate"),
        "wards_placed":  vision.get("avg_wards_placed"),
        "wards_killed":  vision.get("avg_wards_killed"),
        "gold_diff_10":  laning.get("avg_gold_diff_10"),
        "cs_diff_10":    laning.get("avg_cs_diff_10"),
    }
    return {k: v for k, v in flat.items() if v is not None}


# ──────────────────────────────────────────────
# 비교 결과 생성
# ──────────────────────────────────────────────

def compare_metrics(
    personal: dict[str, float],
    tier_avg: dict[str, float],
    position: str,
) -> list[dict]:
    """
    개인 지표와 티어 평균을 비교.
    - is_primary: 해당 포지션의 핵심 지표 여부 (약점/강점 판정 대상)
    - diff_pct 내림차순 정렬 (primary 우선)
    """
    profile = POSITION_PROFILES.get(position, _DEFAULT_PROFILE)
    primary_set = set(profile["primary"])

    results = []
    for metric, personal_val in personal.items():
        if metric not in tier_avg:
            continue
        avg_val = tier_avg[metric]
        if avg_val is None or avg_val == 0:
            continue

        diff = round(personal_val - avg_val, 3)
        label, unit, higher_is_better = METRIC_META.get(metric, (metric, "", True))
        above_avg = diff > 0 if higher_is_better else diff < 0

        # 부호 혼재 지표(gold_diff_10, cs_diff_10)는 평균이 0에 가깝거나
        # 부호가 달라 diff_pct가 수백%로 과장될 수 있음 → 절댓값 diff로 대체
        SIGNED_METRICS = {"gold_diff_10", "cs_diff_10"}
        if metric in SIGNED_METRICS or avg_val == 0:
            diff_pct = None  # 퍼센트 미표시
        else:
            diff_pct = round(diff / abs(avg_val) * 100, 1)

        results.append({
            "metric":      metric,
            "label":       label,
            "unit":        unit,
            "personal":    round(personal_val, 2),
            "tier_avg":    round(avg_val, 2),
            "diff":        diff,
            "diff_pct":    diff_pct,
            "above_avg":   above_avg,
            "is_primary":  metric in primary_set,  # 포지션 핵심 지표 여부
        })

    # primary 우선, 그 안에서 diff_pct 절댓값 내림차순
    # diff_pct가 None(부호 혼재 지표)인 경우 diff 절댓값으로 대체
    results.sort(key=lambda x: (
        not x["is_primary"],
        -abs(x["diff_pct"]) if x["diff_pct"] is not None else -abs(x["diff"])
    ))
    return results


# ──────────────────────────────────────────────
# Claude API 입력용 payload 빌드
# ──────────────────────────────────────────────

def build_coach_payload(
    conn: sqlite3.Connection,
    puuid: str,
    tier: str,
    patch_version: Optional[str] = None,
    recent_n: int = 20,
) -> dict:
    """
    Claude API에 넘길 분석 payload 생성.

    patch_version을 명시하지 않으면 tier_averages에 저장된 최신 패치를 자동 사용.
    유저 매치의 game_version이 아닌 tier_averages 기준으로 고정하는 것이 핵심.

    반환 구조:
    {
        "summoner":      { game_name, tag_line, tier, rank, lp },
        "analysis":      get_full_analysis 결과,
        "main_position": str,
        "comparison":    [ {metric, label, personal, tier_avg, diff_pct, above_avg, is_primary} ],
        "weaknesses":    포지션 핵심 지표 중 약점 상위 3개,
        "strengths":     포지션 핵심 지표 중 강점 상위 3개,
        "patch":         str,
    }
    """
    # 항상 tier_averages 기준 최신 패치 사용 (유저 매치 버전과 무관하게 고정)
    if patch_version is None:
        patch_version = get_latest_tier_patch(conn)

    validation = validate_analysis_input(conn, puuid, tier, patch_version)

    summoner = conn.execute(
        "SELECT game_name, tag_line, tier, rank, lp FROM summoners WHERE puuid = ?",
        (puuid,)
    ).fetchone()

    analysis      = get_full_analysis(conn, puuid)
    positions     = analysis.get("positions", [])
    main_position = validation["main_position"]
    personal_flat = _flatten_personal(analysis, main_position)
    tier_avg      = get_tier_averages(conn, tier, main_position, patch_version)
    comparison    = compare_metrics(personal_flat, tier_avg, main_position)

    # 약점/강점은 is_primary=True인 지표만 대상
    primary_only = [r for r in comparison if r["is_primary"]]
    weaknesses   = [r for r in primary_only if not r["above_avg"]][:3]
    strengths    = [r for r in primary_only if r["above_avg"]][:3]

    return {
        "summoner": {
            "game_name": summoner[0] if summoner else "unknown",
            "tag_line":  summoner[1] if summoner else "KR1",
            "tier":      tier,
            "rank":      summoner[3] if summoner else "",
            "lp":        summoner[4] if summoner else 0,
        },
        "analysis":      analysis,
        "main_position": main_position,
        "comparison":    comparison,
        "weaknesses":    weaknesses,
        "strengths":     strengths,
        "patch":         patch_version,
        "warnings":      validation["warnings"],
        "low_sample":    validation["low_sample"],
        "games_analyzed":validation["games"],
    }