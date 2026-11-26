"""A tiny in-memory stand-in for the sync Redis client calls the keyword service makes.

It records every command, so a test can assert 'zero Redis calls'. The limiter tests use the real
Redis from compose.test.yml instead (they assert real TTLs).
"""

from typing import Any


class MemoryRedis:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.ttls: dict[str, int] = {}
        self.commands: list[str] = []

    def _log(self, name: str) -> None:
        self.commands.append(name)

    def exists(self, key: str) -> int:
        self._log("exists")
        return int(key in self.data)

    def get(self, key: str) -> Any:
        self._log("get")
        return self.data.get(key)

    def set(
        self,
        key: str,
        value: Any,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        self._log("set")
        if nx and key in self.data:
            return None
        self.data[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    def incr(self, key: str) -> int:
        self._log("incr")
        self.data[key] = int(self.data.get(key, 0)) + 1
        return int(self.data[key])

    def incrbyfloat(self, key: str, amount: float) -> float:
        self._log("incrbyfloat")
        self.data[key] = float(self.data.get(key, 0.0)) + amount
        return float(self.data[key])

    def expire(self, key: str, seconds: int) -> bool:
        self._log("expire")
        self.ttls[key] = seconds
        return True
