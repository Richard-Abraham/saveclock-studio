"""The SSRF corpus for the only outbound download path (SEC-019, T-2.18).

Every request goes through an in-process MockTransport (nothing leaves the process), except the
TLS-name tests, which talk to a throwaway TLS server on the loopback.
"""

import http.server
import ssl
import subprocess
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.safe_http import (
    DownloadRefused,
    is_public,
    resolve_all,
    safe_download,
)
from saveclock.adapters.stock.download import Downloader, allowed_hosts
from saveclock.adapters.stock.port import PEXELS_HOSTS, StockClip
from saveclock.domain.stock_rules import MAX_DOWNLOAD_BYTES

HOST = "videos.pexels.com"
URL = f"https://{HOST}/video-files/1/a.mp4"
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00" + b"x" * 100
KEY = "work/11111111-1111-4111-8111-111111111111/raw/pexels_1.mp4"
HOSTS = {HOST, "images.pexels.com"}


@pytest.fixture
def blobs(tmp_path: Path) -> FilesystemBlobStore:
    root = tmp_path / "blobs"
    root.mkdir(mode=0o700)
    return FilesystemBlobStore(root, 0)


def resolver_to(address: str | list[str]) -> Callable[[str, int], list[str]]:
    addresses = [address] if isinstance(address, str) else address
    return lambda host, port: addresses


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def ok(body: bytes = MP4, ctype: str = "video/mp4") -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(200, content=body, headers={"content-type": ctype})


def fetch(
    blobs: FilesystemBlobStore,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    url: str = URL,
    address: str | list[str] = "93.184.216.34",
    max_bytes: int = 10_000,
    **kw: object,
) -> int:
    return safe_download(
        url,
        blobs,
        KEY,
        hosts=HOSTS,
        max_bytes=max_bytes,
        resolver=resolver_to(address),
        client=client_for(handler),
        **kw,  # type: ignore[arg-type]
    )


def refused(
    blobs: FilesystemBlobStore, handler: Callable[..., httpx.Response], **kw: object
) -> str:
    with pytest.raises(DownloadRefused) as info:
        fetch(blobs, handler, **kw)  # type: ignore[arg-type]
    assert not blobs.exists(KEY)
    return info.value.reason


def never(request: httpx.Request) -> httpx.Response:  # a request must not even be sent
    raise AssertionError(f"request sent to {request.url}")


def test_a_clean_download_connects_to_the_validated_ip_with_the_host_header(
    blobs: FilesystemBlobStore,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok()(request)

    assert fetch(blobs, handler) == len(MP4)
    assert b"".join(blobs.open(KEY)) == MP4
    assert seen[0].url.host == "93.184.216.34"  # resolve-then-connect: the IP, not the name
    assert seen[0].headers["host"] == HOST
    assert seen[0].extensions["sni_hostname"] == HOST


def test_http_is_refused(blobs: FilesystemBlobStore) -> None:
    assert refused(blobs, never, url=f"http://{HOST}/a.mp4") == "scheme"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/a.mp4",
        "https://10.0.0.5/a.mp4",
        f"https://{HOST}.evil.example/a.mp4",
        "ftp://videos.pexels.com/a.mp4",
    ],
)
def test_a_host_outside_the_allowlist_is_refused(blobs: FilesystemBlobStore, url: str) -> None:
    assert refused(blobs, never, url=url) in {"host_not_allowed", "scheme"}


def test_a_port_other_than_443_is_refused(blobs: FilesystemBlobStore) -> None:
    assert refused(blobs, never, url=f"https://{HOST}:8443/a.mp4") == "port"


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "::1",
        "10.0.0.5",
        "172.17.0.2",
        "192.168.1.10",
        "169.254.169.254",
        "100.64.0.1",
        "fd00::1",
        "0.0.0.0",  # noqa: S104
        "not-an-ip",
    ],
)
def test_a_host_resolving_to_a_non_public_address_is_refused(
    blobs: FilesystemBlobStore, address: str
) -> None:
    assert refused(blobs, never, address=address) == "address"


def test_a_mixed_answer_one_public_one_private_is_refused(blobs: FilesystemBlobStore) -> None:
    assert refused(blobs, never, address=["93.184.216.34", "10.0.0.5"]) == "address"
    assert refused(blobs, never, address=[]) == "address"


def test_a_redirect_to_the_metadata_address_is_refused(blobs: FilesystemBlobStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

    assert refused(blobs, handler) == "scheme"
    assert (
        refused(
            blobs, lambda r: httpx.Response(302, headers={"location": "https://169.254.169.254/x"})
        )
        == "host_not_allowed"
    )


def test_a_redirect_to_an_allowlisted_host_is_revalidated_and_accepted(
    blobs: FilesystemBlobStore,
) -> None:
    hops: list[str] = []
    resolved: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hops.append(request.headers["host"])
        if request.headers["host"] == HOST:
            return httpx.Response(301, headers={"location": "https://images.pexels.com/real.mp4"})
        return ok()(request)

    def resolver(host: str, port: int) -> list[str]:
        resolved.append(host)
        return ["93.184.216.34"]

    assert safe_download(
        URL,
        blobs,
        KEY,
        hosts=HOSTS,
        max_bytes=10_000,
        resolver=resolver,
        client=client_for(handler),
    ) == len(MP4)
    assert hops == [HOST, "images.pexels.com"]
    assert resolved == [HOST, "images.pexels.com"]  # every hop resolves and validates again


def test_a_redirect_to_an_allowlisted_host_that_resolves_privately_is_refused(
    blobs: FilesystemBlobStore,
) -> None:
    def resolver(host: str, port: int) -> list[str]:
        return ["93.184.216.34"] if host == HOST else ["10.0.0.9"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://images.pexels.com/x.mp4"})

    with pytest.raises(DownloadRefused) as info:
        safe_download(
            URL,
            blobs,
            KEY,
            hosts=HOSTS,
            max_bytes=10,
            resolver=resolver,
            client=client_for(handler),
        )
    assert info.value.reason == "address"


def test_a_relative_redirect_stays_on_the_same_host(blobs: FilesystemBlobStore) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("a.mp4"):
            return httpx.Response(302, headers={"location": "/other/b.mp4"})
        return ok()(request)

    assert fetch(blobs, handler) == len(MP4)
    assert calls == ["/video-files/1/a.mp4", "/other/b.mp4"]


def test_more_than_three_redirects_are_refused_and_exactly_three_are_followed(
    blobs: FilesystemBlobStore,
) -> None:
    count = {"n": 0}

    def endless(request: httpx.Request) -> httpx.Response:
        count["n"] += 1
        return httpx.Response(302, headers={"location": f"https://{HOST}/hop{count['n']}.mp4"})

    assert refused(blobs, endless) == "too_many_redirects"
    assert count["n"] == 4  # the first request and three followed hops

    count["n"] = 0

    def three_then_ok(request: httpx.Request) -> httpx.Response:
        count["n"] += 1
        if count["n"] <= 3:
            return httpx.Response(302, headers={"location": f"https://{HOST}/hop{count['n']}.mp4"})
        return ok()(request)

    assert fetch(blobs, three_then_ok) == len(MP4)


def test_a_redirect_without_a_location_is_refused(blobs: FilesystemBlobStore) -> None:
    assert refused(blobs, lambda r: httpx.Response(302)) == "redirect"


def test_content_length_over_the_cap_is_refused_before_any_byte_is_read(
    blobs: FilesystemBlobStore,
) -> None:
    class Boom(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            raise AssertionError("the body was read")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "video/mp4", "content-length": "20000"},
            stream=Boom(),
        )

    assert refused(blobs, handler, max_bytes=10_000) == "too_large"


def test_the_cap_is_100_mb() -> None:
    assert MAX_DOWNLOAD_BYTES == 100 * 1024 * 1024


def test_a_stream_over_the_cap_without_content_length_is_cut_and_nothing_is_left(
    blobs: FilesystemBlobStore, tmp_path: Path
) -> None:
    body = MP4 + b"y" * 50_000
    assert refused(blobs, ok(body), max_bytes=10_000) == "too_large"
    assert list((tmp_path / "blobs").rglob("*.part")) == []


@pytest.mark.parametrize(
    ("ctype", "body", "reason"),
    [
        ("text/html", MP4, "content_type"),
        ("image/png", MP4, "content_type"),
        ("", MP4, "content_type"),
        ("video/mp4", b"<html>" + b"x" * 100, "not_mp4"),
        ("video/mp4", b"\x00\x00\x00\x18ftyp", "not_mp4"),  # shorter than 16 bytes
        ("video/mp4", b"", "not_mp4"),
    ],
)
def test_wrong_content_type_or_magic_bytes_are_refused(
    blobs: FilesystemBlobStore, ctype: str, body: bytes, reason: str
) -> None:
    assert refused(blobs, ok(body, ctype)) == reason


def test_octet_stream_with_mp4_magic_is_accepted_and_charset_is_ignored(
    blobs: FilesystemBlobStore,
) -> None:
    assert fetch(blobs, ok(MP4, "application/octet-stream")) == len(MP4)
    assert fetch(blobs, ok(MP4, "Video/MP4; charset=binary")) == len(MP4)


def test_a_bad_status_a_network_error_and_a_dns_failure_are_refused(
    blobs: FilesystemBlobStore,
) -> None:
    assert refused(blobs, lambda r: httpx.Response(404)) == "http_status"

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    assert refused(blobs, boom) == "network"

    def no_dns(host: str, port: int) -> list[str]:
        raise DownloadRefused("dns")

    with pytest.raises(DownloadRefused) as info:
        safe_download(
            URL, blobs, KEY, hosts=HOSTS, max_bytes=10, resolver=no_dns, client=client_for(never)
        )
    assert info.value.reason == "dns"


def test_cancel_and_the_wall_clock_stop_the_download(blobs: FilesystemBlobStore) -> None:
    assert refused(blobs, ok(), cancel=lambda: True) == "canceled"
    ticks = iter([0.0, 999.0, 999.0])
    assert refused(blobs, ok(), wall_clock_s=10.0, clock=lambda: next(ticks)) == "timeout"


def test_the_default_resolver_and_address_policy() -> None:
    addresses = resolve_all("localhost", 443)
    assert "127.0.0.1" in addresses
    assert not any(is_public(a) for a in addresses)
    assert is_public("93.184.216.34")
    assert not is_public("garbage")
    with pytest.raises(DownloadRefused) as info:
        resolve_all("nonexistent.invalid", 443)
    assert info.value.reason == "dns"


def test_the_downloader_builds_its_hosts_from_the_constant_plus_the_allowlist() -> None:
    assert allowed_hosts() == PEXELS_HOSTS
    assert allowed_hosts(["Extra.Example", " "]) == PEXELS_HOSTS | {"extra.example"}
    with_pixabay = allowed_hosts(pixabay=True)
    assert {"pixabay.com", "cdn.pixabay.com"} <= with_pixabay
    assert not {"pixabay.com"} & allowed_hosts()


def test_a_provider_download_uses_the_downloader(blobs: FilesystemBlobStore) -> None:
    clip = StockClip("pexels", "1", "p", None, None, "L", 1080, 1920, 5.0, None, URL)
    dl = Downloader(resolver=resolver_to("93.184.216.34"), client=client_for(ok()))
    assert dl.fetch(clip, blobs, KEY, max_bytes=10_000, cancel=None) == len(MP4)
    bad = Downloader(resolver=resolver_to("10.0.0.1"), client=client_for(never))
    with pytest.raises(DownloadRefused):
        bad.fetch(clip, blobs, KEY, max_bytes=10_000, cancel=None)


# --- TLS: the certificate is checked against the HOSTNAME even though we connect to an IP ------


def _openssl(*args: str, cwd: Path) -> None:
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603, S607


def _make_cert(directory: Path, name: str, san: str) -> tuple[Path, Path]:
    ext = directory / f"{name}.ext"
    ext.write_text(f"subjectAltName=DNS:{san}\n")
    _openssl(
        "req",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        f"{name}.key",
        "-out",
        f"{name}.csr",
        "-subj",
        f"/CN={san}",
        cwd=directory,
    )
    _openssl(
        "x509",
        "-req",
        "-in",
        f"{name}.csr",
        "-CA",
        "ca.pem",
        "-CAkey",
        "ca.key",
        "-CAcreateserial",
        "-out",
        f"{name}.pem",
        "-days",
        "2",
        "-extfile",
        f"{name}.ext",
        cwd=directory,
    )
    return directory / f"{name}.pem", directory / f"{name}.key"


@pytest.fixture(scope="module")
def pki(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("pki")
    _openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        "ca.key",
        "-out",
        "ca.pem",
        "-days",
        "2",
        "-subj",
        "/CN=test-ca",
        cwd=d,
    )
    _make_cert(d, "good", HOST)
    _make_cert(d, "wrong", "other.example")
    return d


@contextmanager
def serve(pki: Path, name: str) -> Iterator[int]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("content-type", "video/mp4")
            self.send_header("content-length", str(len(MP4)))
            self.end_headers()
            self.wfile.write(MP4)

        def log_message(self, *args: object) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(pki / f"{name}.pem", pki / f"{name}.key")
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()


def tls_fetch(blobs: FilesystemBlobStore, pki: Path, port: int) -> int:
    ctx = ssl.create_default_context(cafile=str(pki / "ca.pem"))
    return safe_download(
        f"https://{HOST}:{port}/a.mp4",
        blobs,
        KEY,
        hosts=HOSTS,
        max_bytes=10_000,
        resolver=resolver_to("127.0.0.1"),
        client=httpx.Client(verify=ctx),
        port=port,
        ip_allowed=lambda a: True,
    )


def test_a_certificate_for_the_right_name_works_through_the_pinned_ip(
    blobs: FilesystemBlobStore, pki: Path
) -> None:
    with serve(pki, "good") as port:
        assert tls_fetch(blobs, pki, port) == len(MP4)


def test_a_certificate_for_another_name_fails_even_when_the_ip_is_pinned(
    blobs: FilesystemBlobStore, pki: Path
) -> None:
    with serve(pki, "wrong") as port, pytest.raises(DownloadRefused) as info:
        tls_fetch(blobs, pki, port)
    assert info.value.reason == "network"
    assert not blobs.exists(KEY)
