"""SEC-168: the CLI talks only to this machine, follows no redirect, sends no Origin."""

import httpx
import pytest

from saveclock.cli.client import ApiError, Client, NetworkError, Refused
from tests.unit.cli_fakes import PID, CliRun, Fake, err, j

BAD_URLS = [
    "http://example.com",
    "http://10.0.0.5:8000",
    "http://localhost.evil.example",
    "http://127.0.0.1@evil.example",
    "http://user:pw@127.0.0.1:8000",
    "ftp://127.0.0.1",
    "http://",
    "127.0.0.1:8000",
]


@pytest.mark.unit
@pytest.mark.parametrize("url", BAD_URLS)
def test_a_url_that_is_not_this_machine_is_refused_before_any_request(url: str) -> None:
    fake = Fake()
    with pytest.raises(Refused) as exc:
        Client(url, transport=httpx.MockTransport(fake.handler))
    assert exc.value.exit_code == 2
    assert fake.requests == []


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    ["http://localhost:8000", "http://127.0.0.1:8000", "http://[::1]:8000", "HTTP://LOCALHOST"],
)
def test_loopback_urls_are_accepted(url: str) -> None:
    Client(url, transport=httpx.MockTransport(Fake().handler)).close()


@pytest.mark.unit
def test_a_refused_url_builds_no_transport(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from saveclock.cli import main as cli_main

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("an HTTP client was built for a refused URL")

    monkeypatch.setattr(httpx, "Client", boom)
    assert cli_main.main(["--api-url", "http://example.com", "status"]) == 2
    assert "refus" in capsys.readouterr().err


@pytest.mark.unit
@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_a_redirect_is_refused_with_exactly_one_request(status: int) -> None:
    fake = Fake().on(
        "GET",
        f"/projects/{PID}",
        httpx.Response(status, headers={"location": "http://evil.example/x"}),
    )
    c = fake.client()
    with pytest.raises(Refused) as exc:
        c.call("get_project", params={"project_id": PID})
    assert exc.value.exit_code == 3
    assert exc.value.code == "redirect"
    assert len(fake.requests) == 1


@pytest.mark.unit
def test_a_redirect_to_the_same_host_is_refused_too() -> None:
    fake = Fake().on(
        "GET",
        f"/projects/{PID}",
        httpx.Response(302, headers={"location": f"/api/v1/projects/{PID}"}),
    )
    with pytest.raises(Refused):
        fake.client().call("get_project", params={"project_id": PID})
    assert len(fake.requests) == 1


@pytest.mark.unit
def test_a_response_without_an_envelope_is_internal_error() -> None:
    fake = Fake().on("GET", f"/projects/{PID}", httpx.Response(500, text="<html>boom</html>"))
    with pytest.raises(ApiError) as exc:
        fake.client().call("get_project", params={"project_id": PID})
    assert exc.value.code == "internal_error"
    assert exc.value.status == 500


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "bad_request"), (404, "not_found"), (409, "conflict"), (413, "payload_too_large"),
        (415, "unsupported_media"), (422, "file_rejected"), (500, "internal_error"),
        (503, "upstream_unavailable"), (507, "insufficient_storage"),
    ],
)  # fmt: skip
def test_every_error_status_prints_the_envelope_code_and_exits_1(
    status: int, code: str, cli_run: CliRun
) -> None:
    fake = Fake().on("GET", f"/projects/{PID}", err(status, code, reason="x"))
    exit_code, _out, errout = cli_run(fake, "status", PID)
    assert exit_code == 1
    assert f"error: {code}" in errout


@pytest.mark.unit
def test_requests_carry_no_origin_cookie_or_credential() -> None:
    fake = Fake().on("GET", f"/projects/{PID}", j(200, {}))
    fake.client().call("get_project", params={"project_id": PID})
    headers = {k.lower() for k in fake.requests[0].headers}
    assert not headers & {"origin", "cookie", "authorization", "proxy-authorization"}
    assert fake.requests[0].headers["user-agent"].startswith("saveclock-cli/")


@pytest.mark.unit
def test_a_timeout_is_a_network_error_exit_3(cli_run: CliRun) -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    fake = Fake().on("GET", f"/projects/{PID}", slow)
    code, _out, errout = cli_run(fake, "status", PID)
    assert code == 3
    assert "network_error" in errout
    with pytest.raises(NetworkError):
        fake.client().call("get_project", params={"project_id": PID})


@pytest.mark.unit
def test_an_id_that_is_not_a_uuid_never_reaches_a_url(cli_run: CliRun) -> None:
    fake = Fake()
    code, _out, errout = cli_run(fake, "status", "../../etc")
    assert code == 2
    assert "not an id" in errout
    assert fake.requests == []
