"""
Claude API 호출 및 코치 피드백 반환.

시스템 프롬프트에 prompt caching 적용 — 동일 시스템 프롬프트 반복 호출 시 비용 절감.
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

from src.coach.prompt_builder import SYSTEM_PROMPT, build_user_message

load_dotenv()

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def get_coach_feedback(payload: dict) -> str:
    """
    build_coach_payload() 결과를 받아 Claude 코치 피드백 문자열 반환.
    시스템 프롬프트는 캐싱, 유저 메시지는 플레이어 데이터로 매 요청마다 생성.
    """
    client       = _get_client()
    user_message = build_user_message(payload)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text
