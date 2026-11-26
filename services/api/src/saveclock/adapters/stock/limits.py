"""Rate limit, circuit breaker, retry and search cache for the stock providers (SEC-067, ARCH §10).

Every Redis key made here carries a TTL (the Lua script sets it in the same step as the first
increment, so a crash cannot leave a key that lives forever).
"""

import contextlib
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from urllib.parse import urlsplit

import httpx
import structlog
from redis import Redis

from saveclock.adapters.stock.port import StockClip
from saveclock.errors import StockUnavailable

log = structlog.get_logger()

CACHE_TTL_S = 24 * 3600
WAIT_STEP_S = 1.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
KEY_REJECTED = frozenset({401, 403})
MAX_RETRIES = 3
BACKOFF_START_S = 2.0
BACKOFF_CAP_S = 60.0
# the cheapest correct form of a limit is a counter per window (P5-6)
# shortcut: a fixed window allows a 2x burst at a window edge; upgrade to a Lua token bucket
# if Pexels ever returns 429 in the logs.
ACQUIRE = """
local n = tonumber(redis.call('GET', KEYS[1]) or '0')
if n >= tonumber(ARGV[2]) then return 0 end
n = redis.call('INCR', KEYS[1])
if n == 1 or redis.call('TTL', KEYS[1]) < 0 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return 1
"""


class FixedWindowLimiter:
    def __init__(
        self,
        client: Redis,
        name: str,
        limit: int,
        window_s: int,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client, self.key = client, f"saveclock:rate:{name}"
        self.limit, self.window_s = limit, window_s
        self._sleep, self._clock = sleep, clock

    def try_acquire(self) -> bool:
        return bool(self.client.eval(ACQUIRE, 1, self.key, self.window_s, self.limit))

    def acquire(self, wait_max_s: float = 20.0) -> bool:
        """True when a request may go out; False after waiting `wait_max_s` for the window."""
        deadline = self._clock() + wait_max_s
        while not self.try_acquire():
            if self._clock() >= deadline:
                return False
            self._sleep(WAIT_STEP_S)
        return True


class CircuitBreaker:
    """Opens after `failures` failures within `window_s`; half-opens after `open_s`.

    shortcut: in-process state (one worker process); upgrade to Redis if the worker scales out.
    """

    def __init__(
        self,
        failures: int = 5,
        window_s: float = 30.0,
        open_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failures, self.window_s, self.open_s, self._clock = failures, window_s, open_s, clock
        self._recent: list[float] = []
        self._opened_at: float | None = None
        self._probing = False

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if self._clock() - self._opened_at >= self.open_s and not self._probing:
            self._probing = True  # half-open: exactly one trial request
            return True
        return False

    def release_probe(self) -> None:
        """The half-open trial ended without a verdict (a 4xx, a refusal): allow the next one."""
        self._probing = False

    def record_success(self) -> None:
        self._recent.clear()
        self._opened_at, self._probing = None, False

    def record_failure(self) -> None:
        now = self._clock()
        if self._probing:
            self._opened_at, self._probing = now, False
            return
        self._recent = [t for t in self._recent if now - t <= self.window_s] + [now]
        if len(self._recent) >= self.failures:
            self._opened_at = now


class SearchCache:
    def __init__(self, client: Redis, provider: str) -> None:
        self.client, self.provider = client, provider

    def _key(self, params: dict[str, Any]) -> str:
        canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return f"stock:{self.provider}:{hashlib.sha256(canonical.encode()).hexdigest()}"

    def get(self, params: dict[str, Any]) -> list[StockClip] | None:
        raw = self.client.get(self._key(params))
        if raw is None:
            return None
        return [StockClip(**item) for item in json.loads(raw)]

    def set(self, params: dict[str, Any], clips: list[StockClip]) -> None:
        self.client.set(self._key(params), json.dumps([asdict(c) for c in clips]), ex=CACHE_TTL_S)


class ProviderHttp:
    """GET JSON with the limiter, the breaker and the retry table (ARCH §8: 429/5xx only).

    Never logs or raises a URL (a Pixabay key travels in its query string, P5-11): only host,
    path, status and latency. A rejected key (401/403) is not retried: a revoked key must not
    hammer the API.
    """

    def __init__(
        self,
        http: httpx.Client,
        provider: str,
        limiter: FixedWindowLimiter,
        breaker: CircuitBreaker,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http, self.provider, self.limiter, self.breaker = http, provider, limiter, breaker
        self._sleep = sleep

    def get_json(
        self, url: str, *, params: dict[str, Any], headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        if not self.breaker.allow():
            raise StockUnavailable("stock provider circuit is open", {"reason": "circuit_open"})
        if not self.limiter.acquire():
            self.breaker.release_probe()
            raise StockUnavailable("stock provider rate limit", {"reason": "rate_limited"})
        parts = urlsplit(url)
        for attempt in range(MAX_RETRIES + 1):
            started = time.monotonic()
            response: httpx.Response | None = None
            # a network error is retried like a 5xx; its text could carry the URL
            with contextlib.suppress(httpx.TransportError):
                response = self.http.get(url, params=params, headers=headers or {})
            status = response.status_code if response is not None else None
            log.info(
                "stock.http",
                provider=self.provider,
                host=parts.hostname,
                path=parts.path,
                status=status,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            if response is not None and status == httpx.codes.OK:
                self.breaker.record_success()
                return _json_object(response)
            if status in KEY_REJECTED:
                self.breaker.release_probe()
                raise StockUnavailable("stock provider key rejected", {"reason": "key_rejected"})
            if response is not None and status not in RETRY_STATUSES:
                self.breaker.release_probe()
                raise StockUnavailable("stock provider refused", {"reason": "bad_status"})
            self.breaker.record_failure()
            if attempt < MAX_RETRIES:
                retry_after = response.headers.get("retry-after") if response is not None else None
                self._sleep(_delay(attempt, retry_after))
        raise StockUnavailable("stock provider unavailable", {"reason": "upstream"})


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise StockUnavailable("stock provider sent an unreadable answer", {"reason": "bad_body"})
    return data


def _delay(attempt: int, retry_after: str | None) -> float:
    if retry_after is not None and retry_after.strip().isdigit():
        return min(float(retry_after), BACKOFF_CAP_S)
    return min(BACKOFF_START_S * float(2**attempt), BACKOFF_CAP_S)
