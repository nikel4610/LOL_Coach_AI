# src/analysis/validator.py
"""
분석 파이프라인 진입 전 입력 검증 및 에러 정의.

사용 예:
    from src.analysis.validator import validate_analysis_input, AnalysisError
    validate_analysis_input(conn, puuid, tier)
"""

import sqlite3

# ──────────────────────────────────────────────
# 커스텀 예외 계층
# ──────────────────────────────────────────────

class AnalysisError(Exception):
    """분석 파이프라인 기본 예외"""
    pass

class SummonerNotFoundError(AnalysisError):
    """puuid가 DB에 없음"""
    pass

class InsufficientGamesError(AnalysisError):
    """분석에 필요한 최소 게임 수 미달"""
    def __init__(self, games: int, required: int):
        self.games = games
        self.required = required
        super().__init__(f"게임 수 부족: {games}게임 (최소 {required}게임 필요)")

class TierAverageNotFoundError(AnalysisError):
    """tier_averages에 해당 티어/포지션 데이터 없음"""
    def __init__(self, tier: str, position: str):
        super().__init__(f"티어 평균 데이터 없음: {tier} / {position}")

class InvalidTierError(AnalysisError):
    """유효하지 않은 티어 입력"""
    pass

class DatabaseError(AnalysisError):
    """DB 접근 실패"""
    pass


# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────

VALID_TIERS = {
    "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM",
    "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"
}

MIN_GAMES = 5    # 분석 최소 게임 수
WARN_GAMES = 20  # 이 미만이면 신뢰도 낮음 경고


# ──────────────────────────────────────────────
# 검증 함수
# ──────────────────────────────────────────────

def validate_analysis_input(
    conn: sqlite3.Connection,
    puuid: str,
    tier: str,
    patch_version: str,
    min_games: int = MIN_GAMES,
) -> dict:
    """
    분석 파이프라인 진입 전 전체 검증 수행.

    정상이면 검증 결과 dict 반환:
    {
        "games":        int,   # 실제 게임 수
        "main_position": str,  # 주 포지션
        "low_sample":   bool,  # True면 신뢰도 낮음 경고
        "warnings":     list[str],
    }

    문제 있으면 AnalysisError 계열 예외 raise.
    """
    warnings = []

    # 1. 티어 유효성
    if tier.upper() not in VALID_TIERS:
        raise InvalidTierError(f"유효하지 않은 티어: {tier}")

    # 2. 소환사 존재 여부
    try:
        summoner = conn.execute(
            "SELECT puuid FROM summoners WHERE puuid = ?", (puuid,)
        ).fetchone()
    except sqlite3.Error as e:
        raise DatabaseError(f"DB 조회 실패: {e}") from e

    if not summoner:
        raise SummonerNotFoundError(f"소환사를 찾을 수 없습니다: {puuid[:20]}...")

    # 3. 게임 수 확인
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM match_participants WHERE puuid = ?", (puuid,)
        ).fetchone()
        games = row[0] if row else 0
    except sqlite3.Error as e:
        raise DatabaseError(f"게임 수 조회 실패: {e}") from e

    if games < min_games:
        raise InsufficientGamesError(games, min_games)

    if games < WARN_GAMES:
        warnings.append(
            f"게임 수가 적습니다 ({games}게임). "
            f"{WARN_GAMES}게임 이상일 때 분석 신뢰도가 높아집니다."
        )

    # 4. 주 포지션 확인
    try:
        pos_row = conn.execute(
            """
            SELECT position, COUNT(*) AS cnt
            FROM match_participants
            WHERE puuid = ? AND position IS NOT NULL AND position != ''
            GROUP BY position
            ORDER BY cnt DESC
            LIMIT 1
            """,
            (puuid,)
        ).fetchone()
    except sqlite3.Error as e:
        raise DatabaseError(f"포지션 조회 실패: {e}") from e

    main_position = pos_row[0] if pos_row else None
    if not main_position:
        warnings.append("포지션 데이터가 없습니다. 기본값(MIDDLE)으로 분석합니다.")
        main_position = "MIDDLE"

    # 5. 티어 평균 데이터 존재 여부
    try:
        avg_count = conn.execute(
            """
            SELECT COUNT(*) FROM tier_averages
            WHERE tier = ? AND position = ? AND patch_version = ?
            """,
            (tier.upper(), main_position, patch_version)
        ).fetchone()[0]
    except sqlite3.Error as e:
        raise DatabaseError(f"티어 평균 조회 실패: {e}") from e

    if avg_count == 0:
        # 폴백 가능 여부 확인 (같은 티어 다른 포지션)
        fallback_count = conn.execute(
            "SELECT COUNT(*) FROM tier_averages WHERE tier = ? AND patch_version = ?",
            (tier.upper(), patch_version)
        ).fetchone()[0]

        if fallback_count == 0:
            raise TierAverageNotFoundError(tier, main_position)

        warnings.append(
            f"{tier} {main_position} 포지션 평균 데이터가 없어 "
            f"전체 포지션 평균으로 대체합니다."
        )

    return {
        "games":         games,
        "main_position": main_position,
        "low_sample":    games < WARN_GAMES,
        "warnings":      warnings,
    }