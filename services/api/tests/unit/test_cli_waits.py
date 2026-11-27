"""The CLI's waits are derived from the server's budgets and never cancel anything on timeout."""

import pytest

from saveclock import config
from saveclock.cli import waits
from tests.unit.cli_fakes import PID, RID, CliRun, Fake, j


@pytest.mark.unit
def test_each_wait_outlasts_its_server_limit() -> None:
    assert waits.WAIT_DRAFT_S > config.ANALYZE_LIMIT_S + config.DRAFT_LIMIT_S
    assert waits.WAIT_REPLAN_S > config.DRAFT_LIMIT_S
    assert waits.WAIT_RENDER_S > config.RENDER_LIMIT_S
    assert waits.WAIT_MODE_A_S > config.REMUX_LIMIT_S
    assert max(waits.WAIT_DRAFT_S, waits.WAIT_RENDER_S) <= waits.WAIT_WATCH_S


@pytest.mark.unit
def test_timeout_overrides_the_default_and_exits_3_cancelling_nothing(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    fake = (
        Fake()
        .on("POST", f"/projects/{PID}/renders", j(202, {"render_id": RID}))
        .on("GET", f"/renders/{RID}", j(200, {"state": "running"}))
    )
    code, _out, errout = cli_run(fake, "render", PID, "--timeout", "5")
    assert code == 3
    assert "still running" in errout
    assert PID in errout
    assert sum(cli_clock) == pytest.approx(5, abs=1.0)  # --timeout, not WAIT_RENDER_S
    assert not [o for o in fake.ops if "cancel" in o or o.startswith("DELETE")]
    assert fake.ops[0] == f"POST /projects/{PID}/renders"


@pytest.mark.unit
def test_the_default_render_wait_is_the_derived_one(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    fake = (
        Fake()
        .on("POST", f"/projects/{PID}/renders", j(202, {"render_id": RID}))
        .on("GET", f"/renders/{RID}", j(200, {"state": "running"}))
    )
    code, _out, _err = cli_run(fake, "render", PID)
    assert code == 3
    assert sum(cli_clock) >= waits.WAIT_RENDER_S
