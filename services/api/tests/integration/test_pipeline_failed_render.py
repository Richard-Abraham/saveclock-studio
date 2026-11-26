"""The shared failure hook for the `render` and `remux` stages (plan 007)."""

import json
from collections.abc import Mapping
from typing import NamedTuple
from uuid import UUID

import pytest

from saveclock.domain.events import FailedEvent
from tests.integration.render_harness import Renders

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]

BLOCKED = {
    "checks": [
        {"id": "QM-064", "level": "block", "ok": False, "detail": "max |offset| 2 frame(s)"},
        {"id": "QM-070", "level": "block", "ok": True, "detail": ""},
    ]
}
ONLY_WARNS = {"checks": [{"id": "QM-066", "level": "warn", "ok": False, "detail": ""}]}


class Running(NamedTuple):
    pid: UUID
    rid: UUID
    job: UUID


async def running_render(renderer: Renders, verify: Mapping[str, object] | None) -> Running:
    d = renderer.draft
    pid = await d.drafted()
    rid, job = await renderer.start(pid)
    await d.sql("UPDATE renders SET state = 'running', attempt = 2 WHERE id = $1", rid)
    await d.sql("UPDATE jobs SET state = 'running' WHERE id = $1", job)
    if verify is not None:
        await d.sql("UPDATE renders SET verify = $1::jsonb WHERE id = $2", json.dumps(verify), rid)
    return Running(pid, rid, job)


async def test_a_dead_render_with_a_failed_block_check_is_verification_failed(
    renderer: Renders,
) -> None:
    d = renderer.draft
    pid, rid, job = await running_render(renderer, BLOCKED)
    await renderer.kill_job(job)
    assert await d.status(pid) == ("failed_render", "verification_failed")
    row = await renderer.render_row(rid)
    assert (row["state"], row["error_code"]) == ("failed", "verification_failed")
    assert await d.job(job) == ("dead", "internal_error")
    failed = [e for e in d.recorder.sent if isinstance(e, FailedEvent)]
    assert [(e.stage, e.code, e.retryable) for e in failed] == [
        ("render", "verification_failed", True)
    ]


@pytest.mark.parametrize("verify", [None, ONLY_WARNS])
async def test_a_dead_render_without_a_failed_block_is_an_internal_error(
    renderer: Renders, verify: Mapping[str, object] | None
) -> None:
    d = renderer.draft
    pid, rid, job = await running_render(renderer, verify)
    await renderer.kill_job(job)
    assert await d.status(pid) == ("failed_render", "retries_exhausted")
    row = await renderer.render_row(rid)
    assert (row["state"], row["error_code"]) == ("failed", "internal_error")
    failed = [e for e in d.recorder.sent if isinstance(e, FailedEvent)]
    assert [e.code for e in failed] == ["internal_error"]


async def test_a_dead_remux_fails_mode_a_only(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid = await renderer.ready(pid)
    await renderer.mode_a(rid)
    job = await renderer.job_of(rid, "remux")
    await renderer.kill_job(job)
    row = await renderer.render_row(rid)
    assert (row["state"], row["mode_a_state"]) == ("ready", "failed")
    assert await d.status(pid) == ("ready", None)
    assert await d.job(job) == ("dead", "internal_error")
    assert [e for e in d.recorder.sent if isinstance(e, FailedEvent)] == []


async def test_the_earlier_stages_of_the_hook_are_untouched(renderer: Renders) -> None:
    """A dead draft job still moves `planning` to `failed_plan`, and not a render's project."""
    d = renderer.draft
    pid, djob = await d.analysed()
    await renderer.kill_job(djob)
    assert await d.status(pid) == ("failed_plan", "retries_exhausted")
    assert (await d.sql("SELECT count(*) FROM renders"))[0][0] == 0
