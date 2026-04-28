import asyncio
import time


class RateLimiter:
    """
    Riot API token bucket rate limiter.

    Development Key 기준:
    - 버킷 1: 20 requests / 1초
    - 버킷 2: 100 requests / 120초
    """

    def __init__(self):
        self.buckets = [
            {"capacity": 20,  "tokens": 20,  "refill_rate": 20,  "interval": 1,   "last_refill": time.time()},
            {"capacity": 100, "tokens": 100, "refill_rate": 100, "interval": 120, "last_refill": time.time()},
        ]
        self._lock = asyncio.Lock()

    def _refill(self, bucket: dict):
        now = time.time()
        elapsed = now - bucket["last_refill"]

        if elapsed >= bucket["interval"]:
            bucket["tokens"] = bucket["capacity"]
            bucket["last_refill"] = now

    def _wait_time(self, bucket: dict) -> float:
        """토큰이 충전될 때까지 남은 시간(초) 반환"""
        if bucket["tokens"] >= 1:
            return 0.0
        elapsed = time.time() - bucket["last_refill"]
        return max(0.0, bucket["interval"] - elapsed)

    async def acquire(self):
        """요청 전 반드시 호출. 두 버킷 모두 토큰 확보 후 반환."""
        async with self._lock:
            while True:
                for bucket in self.buckets:
                    self._refill(bucket)

                wait_times = [self._wait_time(b) for b in self.buckets]
                max_wait = max(wait_times)

                if max_wait == 0:
                    for bucket in self.buckets:
                        bucket["tokens"] -= 1
                    return

                await asyncio.sleep(max_wait + 0.05)  # 약간의 여유 추가
