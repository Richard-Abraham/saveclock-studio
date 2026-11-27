"""Rehydration (plan 008, Step 4): a swept project still renders, from an unchanged plan."""

import json
import time
from typing import Any
from uuid import UUID

import pytest
from redis import Redis

from saveclock.adapters.stock.fake import FakeStockProvider
from saveclock.config import RENDER_REHYDRATE_S
from saveclock.domain.events import ProgressEvent
from saveclock.services import footage
from saveclock.services import housekeeping as hkp
from saveclock.services.events import ProgressEmitter
from saveclock.services.footage import build_footage_deps
from saveclock.services.identity import OWNER_USER_ID
from saveclock.services.rehydrate import rehydrate_plan
from tests.integration.draft_harness import Draft
from tests.integration.render_harness import Renders

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]


class SpyRanker:
    """Any call is a re-rank: rehydration must never embed or rank."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        self.calls.append(name)
        msg = f"rehydration must not rank: {name}"
        raise AssertionError(msg)


async def plan_hash(d: Draft, pid: UUID) -> str:
    row = await d.sql(
        "SELECT content_hash, version FROM edit_plans WHERE project_id=$1 ORDER BY version DESC",
        pid,
    )
    return f"{bytes(row[0][0]).hex()}:{row[0][1]}"


async def sweep_now(d: Draft, pid: UUID) -> None:
    report = await hkp.sweep_intermediates(d.ctx, OWNER_USER_ID, project_id=pid)
    assert report.projects == [pid]
    assert not d.ctx.blobs.list(f"work/{pid}")


async def test_a_swept_project_renders_again_from_an_unchanged_plan(
    renderer: Renders, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    spy = SpyRanker()  # installed after the draft, which ranks: only rehydration is watched
    monkeypatch.setattr(footage, "get_ranker", lambda _settings: spy)
    before = await plan_hash(d, pid)
    plan = await d.plan(pid)
    statuses = await d.sql(
        "SELECT status FROM clip_candidates WHERE project_id=$1 AND status='selected'", pid
    )
    assert statuses  # the plan's clips are `selected`
    await sweep_now(d, pid)
    purged = await d.sql("SELECT intermediates_purged_at FROM projects WHERE id=$1", pid)
    assert purged[0][0] is not None

    rid, job = await renderer.start(pid)  # no 409: the job fetches the clips again
    await renderer.run_render(job)

    row = await renderer.render_row(rid)
    assert row["state"] == "ready", row
    assert await plan_hash(d, pid) == before  # the plan is the stored one, untouched
    for cut in plan.cuts:
        assert d.ctx.blobs.exists(cut.clip.mezzanine_key)
    selected = {
        (r[0], r[1])
        for r in await d.sql(
            "SELECT provider, provider_id FROM clip_candidates"
            " WHERE project_id=$1 AND status='selected'",
            pid,
        )
    }
    assert selected == {(c.clip.provider, c.clip.provider_id) for c in plan.cuts}
    after = await d.sql("SELECT intermediates_purged_at FROM projects WHERE id=$1", pid)
    assert after[0][0] is None  # eligible for the next sweep after 7 more idle days
    steps = [e.step for e in d.recorder.sent if isinstance(e, ProgressEvent)]
    assert "restoring_clips" in steps
    assert steps.index("restoring_clips") < steps.index("rendering")
    assert spy.calls == []  # no rank, no embedding


async def test_a_clip_gone_at_the_provider_ends_the_render_and_flags_the_cuts(
    renderer: Renders, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    before = await plan_hash(d, pid)
    plan = await d.plan(pid)
    victim = plan.cuts[0].clip.provider_id
    real = FakeStockProvider.video_by_id
    monkeypatch.setattr(
        FakeStockProvider,
        "video_by_id",
        lambda self, pid_: None if pid_ == victim else real(self, pid_),
    )
    await sweep_now(d, pid)

    rid, job = await renderer.start(pid)
    await renderer.run_render(job)

    row = await renderer.render_row(rid)
    assert (row["state"], row["error_code"]) == ("failed", "clip_unavailable")
    assert await d.status(pid) == ("draft_ready", "clip_unavailable")
    flags = json.loads((await d.sql("SELECT flags FROM projects WHERE id=$1", pid))[0][0])
    expected = sorted(c.index for c in plan.cuts if c.clip.provider_id == victim)
    assert flags["clip_unavailable"] == {"version": plan.version, "cuts": expected}
    assert await plan_hash(d, pid) == before
    state = (await d.sql("SELECT state, error_code FROM jobs WHERE id=$1", job))[0]
    assert tuple(state) == ("error", "clip_unavailable")


async def test_a_replan_after_a_sweep_still_produces_a_plan(draft: Draft) -> None:
    """Stored candidates are reused without their embeddings (Step 4 item 5)."""
    from saveclock.services.draft import run_draft

    pid = await draft.drafted()
    await sweep_now(draft, pid)
    r = await draft.client.patch(
        f"/api/v1/projects/{pid}/plan",
        json={"base_version": 1, "ops": [{"op": "set_keywords", "keywords": ["red", "green"]}]},
    )
    assert r.status_code == 202, r.text
    job = UUID(r.json()["job_id"])
    await run_draft(draft.ctx, job, OWNER_USER_ID, mode="replan")
    assert await draft.job(job) == ("ok", None)
    assert await draft.status(pid) == ("draft_ready", None)
    plan = await draft.plan(pid)  # the stored candidates were reused: a valid plan, no embeddings
    assert plan.cuts


async def test_rehydration_time_of_a_swept_plan_is_measured(
    renderer: Renders, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    monkeypatch.setattr(footage, "get_ranker", lambda _settings: SpyRanker())
    plan = await d.plan(pid)
    await sweep_now(d, pid)
    redis: Redis = Redis.from_url(d.ctx.settings.redis_url.get_secret_value())
    deps = build_footage_deps(d.ctx, redis, pixabay_on=False)
    started = time.monotonic()
    try:
        rebuilt = await rehydrate_plan(
            deps,
            plan,
            user_id=OWNER_USER_ID,
            project_id=pid,
            emitter=ProgressEmitter(None, pid),
            deadline_s=RENDER_REHYDRATE_S,
        )
    finally:
        deps.close()
        redis.close()
    seconds = time.monotonic() - started
    with capsys.disabled():
        print(
            f"\nREHYDRATION: {len(plan.cuts)} cuts, {rebuilt} clips rebuilt in {seconds:.1f} s "
            f"(budget {RENDER_REHYDRATE_S} s)"
        )
    assert rebuilt >= 1
    assert seconds < RENDER_REHYDRATE_S / 2  # the plan's STOP threshold
