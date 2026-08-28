"""
외부 조회 결과를 잠시 들고 있는 캐시.
"""
from __future__ import annotations

import logging
import threading
import time

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class Entry:
    value: Any
    stored_at: float


class TTLCache:
    """
    키별로 값을 TTL 동안 재사용한다.

    FastAPI의 동기 엔드포인트는 스레드풀에서 돌아가므로 여러 요청이 동시에
    들어온다. 락으로 감싸지 않으면 캐시가 비어 있는 순간 같은 외부 호출이
    동시에 여러 번 나간다.
    """

    def __init__(self, ttl_s: float, name: str = "cache"):
        self.ttl_s = ttl_s
        self.name = name
        self._data: Dict[str, Entry] = {}
        self._lock = threading.Lock()
        # 키별 락. 전역 락으로 외부 호출까지 감싸면, 한 지역을 부르는 동안
        # 다른 지역 요청까지 멈춘다.
        self._key_locks: Dict[str, threading.Lock] = {}

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def peek(self, key: str) -> Tuple[Optional[Any], Optional[float]]:
        """저장된 값과 나이(초). 만료 여부와 무관하게 돌려준다."""
        with self._lock:
            e = self._data.get(key)
        if e is None:
            return None, None
        return e.value, time.monotonic() - e.stored_at

    def get_or_load(
        self,
        key: str,
        loader: Callable[[], Optional[T]],
    ) -> Tuple[Optional[T], float, bool]:
        """
        신선한 값이 있으면 그대로, 없으면 loader를 부른다.

        반환: (값, 나이 초, 캐시에서 온 것인지)

        loader가 None을 돌려주거나 예외를 던지면 만료된 값이라도 있으면
        그것을 쓴다. 그래서 외부 API가 죽어도 화면이 비지 않는다.
        """
        value, age = self.peek(key)
        if value is not None and age is not None and age < self.ttl_s:
            return value, age, True

        # 같은 키에 대한 갱신은 한 번만 나가게 한다.
        with self._key_lock(key):
            # 락을 기다리는 동안 다른 스레드가 채웠을 수 있다.
            value2, age2 = self.peek(key)
            if value2 is not None and age2 is not None and age2 < self.ttl_s:
                return value2, age2, True

            try:
                fresh = loader()
            except Exception:
                logger.exception("%s 갱신 실패 key=%s", self.name, key)
                fresh = None

            if fresh is not None:
                with self._lock:
                    self._data[key] = Entry(fresh, time.monotonic())
                return fresh, 0.0, False

            # 갱신 실패. 오래된 값이라도 있으면 쓴다.
            if value2 is not None:
                logger.warning("%s 갱신 실패, %.0f초 지난 값을 사용 key=%s",
                               self.name, age2 or 0, key)
                return value2, age2 or 0.0, True

            return None, 0.0, False

    def invalidate(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._data.clear()
            else:
                self._data.pop(key, None)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            return {
                "name": self.name,
                "ttl_s": self.ttl_s,
                "keys": {k: round(now - e.stored_at, 1) for k, e in self._data.items()},
            }