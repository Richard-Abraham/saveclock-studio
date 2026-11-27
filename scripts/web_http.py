"""Tiny HTTP helpers shared by smoke_web.py and measure_rewrite.py. Stdlib only."""

import http.client
from urllib.parse import urlsplit


def connect(base: str, timeout: float = 120) -> http.client.HTTPConnection:
    parts = urlsplit(base)
    return http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)


def fetch(
    base: str, method: str, path: str, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, str], str]:
    """One request: (status, lowercase response headers, body text)."""
    conn = connect(base, 15)
    try:
        conn.request(method, path, headers=headers or {})
        response = conn.getresponse()
        body = response.read().decode("utf-8", "replace")
        return response.status, {k.lower(): v for k, v in response.getheaders()}, body
    finally:
        conn.close()


def preflight(base: str, origin: str, path: str = "/api/v1/_measure/upload-sink") -> tuple[int, str | None]:
    """CORS preflight as the browser sends it: (status, Access-Control-Allow-Origin or None)."""
    status, headers, _ = fetch(
        base,
        "OPTIONS",
        path,
        {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-filename",
        },
    )
    return status, headers.get("access-control-allow-origin")
