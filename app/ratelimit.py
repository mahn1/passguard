"""Ограничение частоты запросов по IP: защищает вход и регистрацию от перебора."""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Скользящее окно в памяти процесса. Для одного инстанса этого достаточно, для нескольких нужен Redis."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry = int(self.window - (now - hits[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Слишком много попыток. Повторите через {retry} с",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limit = RateLimiter(limit=10, window_seconds=5 * 60)
register_limit = RateLimiter(limit=5, window_seconds=60 * 60)
demo_limit = RateLimiter(limit=10, window_seconds=60 * 60)
ALL = (login_limit, register_limit, demo_limit)
