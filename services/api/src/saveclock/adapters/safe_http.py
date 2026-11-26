"""The one outbound download path (SEC-019, T-2.18): resolve, validate, then connect to that IP.

* https only, port 443, host in the allowlist, on the first request and on every redirect hop;
* every address the name resolves to must be global (no RFC1918, loopback, link-local, CGNAT,
  multicast, metadata, Docker networks); one private answer among public ones refuses the host;
* the request goes to the validated IP with the hostname as Host header and TLS server name, so a
  DNS answer that changes between the check and the connect cannot redirect it, and the
  certificate is still checked against the hostname;
* redirects are followed by hand (at most 3); the body is streamed into the blob store with a hard
  size cap, a content-type check and an mp4 magic-byte sniff; a wall-clock limit and cancel apply.
"""

import ipaddress
import socket
import time
from collections.abc import Callable, Iterable, Iterator
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.errors import PayloadTooLarge

MAX_REDIRECTS = 3
HTTPS_PORT = 443
CHUNK = 64 * 1024
WALL_CLOCK_S = 300.0
CONNECT_TIMEOUT_S = 10.0
SNIFF_BYTES = 16
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
OK_TYPES = ("video/", "application/octet-stream")

Resolver = Callable[[str, int], list[str]]
IpPolicy = Callable[[str], bool]


class DownloadRefused(Exception):
    """A download was refused or failed; `reason` is a short stable code, never a URL."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def resolve_all(host: str, port: int) -> list[str]:
    """Every address of the host (the default resolver)."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise DownloadRefused("dns") from exc
    return sorted({str(info[4][0]) for info in infos})


def is_public(address: str) -> bool:
    """True only for a globally routable address (this rejects every private, loopback,
    link-local, CGNAT, multicast and metadata address)."""
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def _check_url(url: str, hosts: frozenset[str], port: int) -> tuple[str, str]:
    """(hostname, path-and-query) of a URL that passes the scheme, host and port rules."""
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise DownloadRefused("scheme")
    host = (parts.hostname or "").lower()
    if host not in hosts:
        raise DownloadRefused("host_not_allowed")
    if (parts.port or HTTPS_PORT) != port:
        raise DownloadRefused("port")
    path = parts.path or "/"
    return host, f"{path}?{parts.query}" if parts.query else path


def _pick_address(host: str, port: int, resolver: Resolver, ip_allowed: IpPolicy) -> str:
    addresses = resolver(host, port)
    if not addresses or not all(ip_allowed(a) for a in addresses):
        raise DownloadRefused("address")
    return addresses[0]


def _ip_url(address: str, port: int, path: str) -> str:
    bracketed = f"[{address}]" if ":" in address else address
    return f"https://{bracketed}:{port}{path}"


def _chunks(
    response: httpx.Response,
    *,
    deadline: float,
    cancel: Callable[[], bool] | None,
    clock: Callable[[], float],
) -> Iterator[bytes]:
    head = b""
    for chunk in response.iter_bytes(CHUNK):
        if clock() > deadline:
            raise DownloadRefused("timeout")
        if cancel is not None and cancel():
            raise DownloadRefused("canceled")
        if len(head) < SNIFF_BYTES:
            head += chunk[: SNIFF_BYTES - len(head)]
            if len(head) >= SNIFF_BYTES and head[4:8] != b"ftyp":
                raise DownloadRefused("not_mp4")
        yield chunk
    if len(head) < SNIFF_BYTES or head[4:8] != b"ftyp":
        raise DownloadRefused("not_mp4")


def safe_download(
    url: str,
    blobs: BlobStore,
    key: str,
    *,
    hosts: Iterable[str],
    max_bytes: int,
    resolver: Resolver = resolve_all,
    cancel: Callable[[], bool] | None = None,
    client: httpx.Client | None = None,
    port: int = HTTPS_PORT,
    ip_allowed: IpPolicy = is_public,
    wall_clock_s: float = WALL_CLOCK_S,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Download `url` into the blob `key`; returns the byte count. Raises `DownloadRefused`.

    `port`, `ip_allowed`, `client` and `clock` are seams for tests (a local TLS server, a mock
    transport); production calls use the defaults: port 443, public addresses only.
    """
    allowed = frozenset(h.lower() for h in hosts)
    http = client or httpx.Client(timeout=httpx.Timeout(30.0, connect=CONNECT_TIMEOUT_S))
    deadline = clock() + wall_clock_s
    current = url
    try:
        for hop in range(MAX_REDIRECTS + 1):
            host, path = _check_url(current, allowed, port)
            address = _pick_address(host, port, resolver, ip_allowed)
            request = http.build_request(
                "GET",
                _ip_url(address, port, path),
                headers={"Host": host, "Accept": "video/*"},
                extensions={"sni_hostname": host},
            )
            response = http.send(request, stream=True, follow_redirects=False)
            try:
                if response.status_code in REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise DownloadRefused("redirect")
                    if hop == MAX_REDIRECTS:
                        raise DownloadRefused("too_many_redirects")
                    current = urljoin(current, location)
                    continue
                return _store(
                    response,
                    blobs,
                    key,
                    max_bytes=max_bytes,
                    deadline=deadline,
                    cancel=cancel,
                    clock=clock,
                )
            finally:
                response.close()
    except httpx.HTTPError as exc:
        raise DownloadRefused("network") from exc
    finally:
        if client is None:
            http.close()
    raise DownloadRefused("redirect")  # pragma: no cover - the loop returns or raises


def _store(
    response: httpx.Response,
    blobs: BlobStore,
    key: str,
    *,
    max_bytes: int,
    deadline: float,
    cancel: Callable[[], bool] | None,
    clock: Callable[[], float],
) -> int:
    if response.status_code != httpx.codes.OK:
        raise DownloadRefused("http_status")
    ctype = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not ctype.startswith(OK_TYPES):
        raise DownloadRefused("content_type")
    declared: Any = response.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise DownloadRefused("too_large")
    try:
        return blobs.put(
            key,
            _chunks(response, deadline=deadline, cancel=cancel, clock=clock),
            max_bytes=max_bytes,
        )
    except PayloadTooLarge as exc:
        raise DownloadRefused("too_large") from exc
