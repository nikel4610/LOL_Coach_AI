"""
Claude API에 넘길 시스템 프롬프트 및 유저 메시지 생성.

시스템 프롬프트는 변경이 드물어 프롬프트 캐싱 대상.
유저 메시지는 플레이어별 데이터로 매 요청마다 달라짐.
"""

ROLE_GROUP_KR = {
    "dealer":         "딜러형",
    "fighter":        "파이터형",
    "tank":           "탱커형",
    "enchanter":      "인챈터",
    "engage_support": "이니시에이터 서폿",
    "damage_support": "딜 서폿",
    "jungle":         "정글",
}

POSITION_KR = {
    "TOP":     "탑",
    "JUNGLE":  "정글",
    "MIDDLE":  "미드",
    "BOTTOM":  "원딜",
    "UTILITY": "서폿",
}

POSITION_CONTEXT = {
    "TOP":     "탑 라이너는 독립적인 라인 파밍(CS)과 팀 합류 타이밍이 핵심입니다. 탱커/파이터 여부에 따라 딜 비중은 크게 달라질 수 있습니다.",
    "JUNGLE":  "정글러는 킬 관여율과 비전 컨트롤이 승패에 직결됩니다. 와드 제거로 시야 싸움에서 우위를 점하는 것이 중요합니다.",
    "MIDDLE":  "미드 라이너는 CS 파밍, 딜 기여, 그리고 적극적인 로밍으로 팀 전반의 흐름을 이끌어야 합니다.",
    "BOTTOM":  "원딜은 안정적인 CS 파밍으로 후반 딜 캐리를 준비하는 것이 최우선입니다. 딜 비중이 낮으면 팀 화력에 기여하지 못합니다.",
    "UTILITY": "서포터는 시야 장악(와드 설치/제거)과 높은 킬 관여율로 팀의 눈과 전투력을 책임집니다.",
}

SYSTEM_PROMPT = """당신은 리그 오브 레전드 전문 코치입니다. 플레이어의 통계 데이터를 분석해 실질적이고 구체적인 개선 조언을 제공합니다.

## 피드백 원칙
- 약점은 직접적으로 짚되 개선 방법을 구체적으로 제시할 것
- 강점은 인정하고 유지/심화 방법을 짧게 조언할 것
- 해당 티어에 맞는 현실적인 목표 제시
- 전문 용어(CS, 갱킹, 로밍 등)는 자연스럽게 사용

## 출력 형식 (한국어, 마크다운)

**종합 평가**
현재 플레이어의 전반적인 수준과 특징을 2~3문장으로 요약.

**개선 포인트**
약점 지표 기반으로 2~3가지. 각 항목은 왜 중요한지 + 어떻게 개선할지 포함.

**잘하고 있는 점**
강점 지표 기반으로 1~2가지. 강점을 유지하거나 심화할 방법 한 줄.

**이번 주 집중 과제**
가장 빠르게 실력 향상으로 이어질 단 하나의 과제만 제시."""


def _fmt_metric(r: dict) -> str:
    unit = r["unit"]
    pct = f"{r['diff_pct']:+.1f}%" if r["diff_pct"] is not None else f"diff {r['diff']:+.1f}"
    arrow = "▲" if r["above_avg"] else "▼"
    return f"- {r['label']}: {r['personal']}{unit} (티어 평균 {r['tier_avg']}{unit}, {arrow}{pct})"


def _build_phase_text(phase: dict) -> str:
    if not phase:
        return "- (타임라인 데이터 없음)"
    lines = []
    for minute in [5, 10, 14, 20, 25]:
        cs = phase.get(f"cs_at_{minute}")
        gd = phase.get(f"gold_diff_{minute}")
        if cs is None:
            continue
        gd_str = f" / 골드차 {gd:+.0f}" if gd is not None else ""
        lines.append(f"- {minute}분: CS {cs}{gd_str}")
    return "\n".join(lines) if lines else "- (타임라인 데이터 없음)"


def _build_event_text(events: dict) -> str:
    lines = []

    back = events.get("avg_first_back_min")
    if back:
        lines.append(f"- 평균 첫 귀환: {back}분")

    objs = events.get("objectives", [])
    if objs:
        lines.append("\n[오브젝트 팀 확보율]")
        for o in objs:
            lines.append(
                f"- {o['type_kr']}: 평균 {o['avg_minute']}분 스폰 "
                f"/ 내 팀 확보 {o['secure_rate']}% ({o['team_secured']}/{o['total_games']}게임)"
            )

    towers = events.get("towers", [])
    if towers:
        lines.append("\n[라인별 첫 포탑 타이밍]")
        for t in towers:
            lines.append(
                f"- {t['lane_kr']} 라인: 평균 {t['avg_minute']}분 "
                f"/ 우리팀 먼저 {t['first_rate']}% ({t['my_team_first']}/{t['total_games']}게임)"
            )

    return "\n".join(lines) if lines else "- (이벤트 데이터 없음)"


def build_user_message(payload: dict) -> str:
    s        = payload["summoner"]
    position = payload["main_position"]
    pos_kr   = POSITION_KR.get(position, position)
    context  = POSITION_CONTEXT.get(position, "")

    primary_rows = [r for r in payload["comparison"] if r["is_primary"]]
    weaknesses   = payload["weaknesses"]
    strengths    = payload["strengths"]

    event_text   = _build_event_text(payload.get("analysis", {}).get("events", {}))
    phase_text   = _build_phase_text(payload.get("analysis", {}).get("phase", {}))
    metrics_text = "\n".join(_fmt_metric(r) for r in primary_rows) or "- (데이터 없음)"

    if weaknesses:
        weak_text = "\n".join(_fmt_metric(r) for r in weaknesses)
    else:
        weak_text = "- 없음 (모든 핵심 지표가 평균 이상)"

    if strengths:
        str_text = "\n".join(_fmt_metric(r) for r in strengths)
    else:
        str_text = "- 없음"

    warnings_text = ""
    if payload.get("warnings"):
        warnings_text = "\n⚠ " + "\n⚠ ".join(payload["warnings"]) + "\n"
    if payload.get("low_sample"):
        warnings_text += "\n⚠ 분석 게임 수가 적어 신뢰도가 낮을 수 있습니다."

    role_kr  = ROLE_GROUP_KR.get(payload.get("role_group", ""), "")
    main_champ = payload.get("main_champion", "")
    champ_line = f"\n- 챔피언 유형: {role_kr} ({main_champ})" if role_kr and main_champ else ""

    return f"""## 플레이어 정보
- 소환사명: {s['game_name']}#{s['tag_line']}
- 티어: {s['tier']} {s['rank']} ({s['lp']}LP)
- 주 포지션: {pos_kr}{champ_line}
- 분석 게임 수: {payload['games_analyzed']}게임
- 기준 패치: {payload['patch']}
{warnings_text}
## 포지션 특성
{context}

## 핵심 지표 비교 (동티어 {pos_kr} 평균 대비)
{metrics_text}

## 약점
{weak_text}

## 강점
{str_text}

## 라인전 단계별 성장 지표 (분당 CS·골드차 추이)
{phase_text}

## 게임 이벤트 통계

{event_text}

위 데이터를 바탕으로 코치 피드백을 작성해주세요."""
