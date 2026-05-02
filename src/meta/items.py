"""
DDragon 아이템 데이터 로컬 캐시.
최초 실행 시 API에서 받아와 data/raw/items.json에 저장.
"""

import json
import requests
from pathlib import Path

CACHE_PATH = Path("data/raw/items.json")
DDRAGON_VERSION_URL = "https://ddragon.leagueoflegends.com/api/versions.json"


def _fetch_and_cache() -> dict[int, str]:
    versions = requests.get(DDRAGON_VERSION_URL, timeout=10).json()
    latest = versions[0]
    url = f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/ko_KR/item.json"
    data = requests.get(url, timeout=10).json()

    items = {int(iid): info["name"] for iid, info in data["data"].items()}
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    return items


def load_item_names() -> dict[int, str]:
    """아이템 ID → 한국어 이름 dict 반환. 캐시 없으면 DDragon에서 받아옴."""
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}
    return _fetch_and_cache()


# 시작 아이템 / 와드 / 신발 등 아이템 분류
STARTING_ITEMS = {
    1055, 1056, 1057, 1082, 1083, 2003, 2010, 2033, 3340, 3364, 3363,
    1101, 1102, 1103,  # 정글 시작템
    2422,  # 점화의 망토
}

COMPONENT_PRICE_THRESHOLD = 1000  # 이 가격 이하는 부품 취급 (아이템 DB 없을 때 fallback)
