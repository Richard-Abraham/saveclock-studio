"""The draft job in-process: stages, outcomes, failures, cancel, idempotency and replan."""

import itertools
import json
from pathlib import Path
from uuid import UUID

import pytest

from saveclock.adapters.stock.fake import FakeStockProvider
from saveclock.domain.plan_validator import blocking, validate_plan
from saveclock.domain.planner import PlanError
from saveclock.errors import StockUnavailable
from saveclock.services.draft import STAGES, run_draft
from tests.integration.draft_harness import OWNER, Draft

pytestmark = pytest.mark.integration


async def test_the_first_draft_ends_in_a_valid_plan(draft: Draft) -> None:
    pid, djob = await draft.analysed()
    assert await draft.status(pid) == ("planning", None)
    await run_draft(draft.ctx, djob, OWNER, mode="draft")
    assert await draft.status(pid) == ("draft_ready", None)
    assert await draft.job(djob) == ("ok", None)
    plan = await draft.plan(pid)
    assert (plan.version, plan.total_frames, plan.created_by) == (1, 900, "planner")
    assert plan.provenance.keyword_source == "table"  # no key and no override: offline (FR-050)
    found = validate_plan(plan, allow_repeats=True, beats_s=plan.beat_grid.beats_s)
    assert blocking(found) == []
    assert all(c.clip.attribution.page_url.startswith("https://") for c in plan.cuts)


async def test_every_stage_is_timed_in_order_and_progress_never_goes_back(draft: Draft) -> None:
    _pid, djob = await draft.analysed()
    draft.recorder.sent.clear()  # the validate and analyze steps are not this job's
    await run_draft(draft.ctx, djob, OWNER, mode="draft")
    row = (await draft.sql("SELECT timings FROM jobs WHERE id = $1", djob))[0]
    timings = json.loads(row[0])
    assert [s["stage"] for s in timings["stages"]] == [n for n, _, _ in STAGES]
    assert timings["total_ms"] >= sum(s["ms"] for s in timings["stages"]) - 5
    kinds = draft.recorder.kinds()
    assert kinds[-2:] == ["state", "draft_ready"]
    pcts = [e.pct for e in draft.recorder.sent if e.type == "progress"]  # type: ignore[union-attr]
    assert pcts == sorted(pcts)
    assert pcts[0] >= 40  # the draft's steps only
    assert pcts[-1] < 100  # below "draft ready"


async def test_the_chosen_clips_are_marked_selected_and_exist(draft: Draft) -> None:
    pid = await draft.drafted()
    plan = await draft.plan(pid)
    used = {(c.clip.provider, c.clip.provider_id) for c in plan.cuts}
    rows = await draft.sql(
        "SELECT provider, provider_id, status FROM clip_candidates WHERE project_id = $1", pid
    )
    selected = {(r[0], r[1]) for r in rows if r[2] == "selected"}
    assert selected == used
    for c in plan.cuts:
        assert (draft.env.blob_root / c.clip.mezzanine_key).is_file()
    assert len({(r[0], r[1]) for r in rows}) == len(rows)  # no duplicate candidate rows


async def test_repeats_happen_only_when_the_pool_is_smaller_than_the_cuts(draft: Draft) -> None:
    pid = await draft.drafted()
    plan = await draft.plan(pid)
    keys = [(c.clip.provider, c.clip.provider_id) for c in plan.cuts]
    flags = json.loads((await draft.sql("SELECT flags FROM projects WHERE id = $1", pid))[0][0])
    assert (len(set(keys)) < len(keys)) == flags["pool_exhausted"]
    assert all(a != b for a, b in itertools.pairwise(keys))


async def test_explicit_keywords_and_a_model_set_the_keyword_source(draft: Draft) -> None:
    explicit = await draft.drafted(keywords_override=["red", "green"])
    assert (await draft.plan(explicit)).provenance.keyword_source == "explicit"
    assert (await draft.plan(explicit)).options.keywords_override == ["red", "green"]


async def test_a_second_run_of_the_same_job_changes_nothing(draft: Draft) -> None:
    _pid, djob = await draft.analysed()
    await run_draft(draft.ctx, djob, OWNER, mode="draft")
    before = await draft.sql("SELECT id, version, content_hash FROM edit_plans")
    await run_draft(draft.ctx, djob, OWNER, mode="draft")  # a redelivery of a finished job
    assert [
        tuple(r) for r in await draft.sql("SELECT id, version, content_hash FROM edit_plans")
    ] == [tuple(r) for r in before]


async def test_a_redelivery_after_the_crash_leaves_exactly_one_plan_version(draft: Draft) -> None:
    """The job was left `running` and the project `planning` (nothing of the first run committed
    except its candidates): the rerun writes version 1 once, from the stored pool."""
    pid, djob = await draft.analysed()
    await run_draft(draft.ctx, djob, OWNER, mode="draft")
    await draft.sql("UPDATE projects SET status = 'planning' WHERE id = $1", pid)
    await draft.sql("UPDATE jobs SET state = 'running' WHERE id = $1", djob)
    await run_draft(draft.ctx, djob, OWNER, mode="draft")
    assert [r[0] for r in await draft.sql("SELECT version FROM edit_plans")] == [1]
    assert await draft.status(pid) == ("draft_ready", None)
    assert await draft.job(djob) == ("ok", None)


async def test_no_usable_clips_fails_the_plan_with_the_stock_error(
    draft: Draft, tmp_path: Path
) -> None:
    empty = tmp_path / "only-landscape"
    empty.mkdir()
    (empty / "landscape.mp4").write_bytes(
        (Path(draft.ctx.settings.fake_stock_dir or "") / "landscape.mp4").read_bytes()
    )
    (empty / "index.json").write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "name": "landscape",
                        "width": 1280,
                        "height": 720,
                        "duration_s": 6.0,
                        "fps": 30,
                    }
                ]
            }
        )
    )
    draft.ctx.settings.fake_stock_dir = str(empty)
    pid, djob = await draft.analysed()
    await run_draft(draft.ctx, djob, OWNER, mode="draft")
    assert await draft.status(pid) == ("failed_plan", "no_usable_clips")
    assert await draft.job(djob) == ("error", "stock_unavailable")
    assert await draft.sql("SELECT 1 FROM edit_plans") == []
    assert draft.recorder.kinds()[-1] == "failed"


async def test_a_stock_outage_fails_the_plan_without_a_retry(
    draft: Draft, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(*_a: object, **_k: object) -> list[object]:
        raise StockUnavailable("provider down")

    monkeypatch.setattr(FakeStockProvider, "search", down)
    pid, djob = await draft.analysed()
    await run_draft(draft.ctx, djob, OWNER, mode="draft")  # returns: Dramatiq would not retry
    assert await draft.status(pid) == ("failed_plan", "stock_unavailable")
    assert await draft.job(djob) == ("error", "stock_unavailable")


async def test_a_cancel_flag_ends_the_job_before_any_work(draft: Draft) -> None:
    _pid, djob = await draft.analysed()
    await draft.sql("UPDATE jobs SET cancel_requested = true WHERE id = $1", djob)
    await run_draft(draft.ctx, djob, OWNER, mode="draft")
    assert await draft.job(djob) == ("error", "canceled")
    assert await draft.sql("SELECT 1 FROM edit_plans") == []
    assert await draft.sql("SELECT 1 FROM clip_candidates") == []


async def test_cancel_in_planning_with_no_plan_then_retry_runs_the_whole_chain(
    draft: Draft,
) -> None:
    """The reviewer's case: the cancel ends the queued draft job (freeing `uq_jobs_active`), and
    the retry later creates a new draft job without anybody deleting a row by hand."""
    pid, djob = await draft.analysed()
    r = await draft.client.post(f"/api/v1/projects/{pid}/cancel")
    assert r.status_code == 202
    assert await draft.status(pid) == ("canceled", None)
    assert await draft.job(djob) == ("error", "canceled")
    await run_draft(draft.ctx, djob, OWNER, mode="draft")  # a late message: nothing to do
    assert await draft.sql("SELECT 1 FROM edit_plans") == []
    assert (await draft.client.post(f"/api/v1/projects/{pid}/retry")).status_code == 202
    retry_job = [a for n, a in draft.env.enqueuer.sent if n == "validate_audio"][-1][0]
    from uuid import UUID

    from saveclock.domain.ids import derive_job_id
    from saveclock.services.analysis import analyze_project
    from saveclock.services.ingest import validate_song

    await validate_song(draft.ctx, UUID(retry_job), OWNER)
    ajob = derive_job_id(UUID(retry_job), "analyze")
    await analyze_project(draft.ctx, ajob, OWNER)
    await run_draft(draft.ctx, derive_job_id(ajob, "draft"), OWNER, mode="draft")
    assert await draft.status(pid) == ("draft_ready", None)
    assert [r[0] for r in await draft.sql("SELECT version FROM edit_plans")] == [1]


async def test_a_failed_plan_is_retried_with_a_new_draft_job(
    draft: Draft, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(*_a: object, **_k: object) -> list[object]:
        raise StockUnavailable("provider down")

    real = FakeStockProvider.search
    monkeypatch.setattr(FakeStockProvider, "search", down)
    pid, djob = await draft.analysed()
    await run_draft(draft.ctx, djob, OWNER, mode="draft")
    assert await draft.status(pid) == ("failed_plan", "stock_unavailable")
    monkeypatch.setattr(FakeStockProvider, "search", real)
    r = await draft.client.post(f"/api/v1/projects/{pid}/retry")
    assert r.status_code == 202
    assert r.json()["ui_status"] == "analysing"
    actor, args = draft.env.enqueuer.sent[-1]
    assert actor == "build_draft"
    assert args[0] != str(djob)  # a fresh job id
    from uuid import UUID

    await run_draft(draft.ctx, UUID(args[0]), OWNER, mode="draft")
    assert await draft.status(pid) == ("draft_ready", None)
    jobs = await draft.sql("SELECT state FROM jobs WHERE stage = 'draft' ORDER BY created_at")
    assert [j[0] for j in jobs] == ["error", "ok"]


async def test_an_analysis_of_a_foreign_project_never_drafts(draft: Draft) -> None:
    pid, djob = await draft.analysed()
    from uuid import UUID

    other = UUID("00000000-0000-4000-8000-0000000000bb")
    await draft.sql("INSERT INTO users (id, email) VALUES ($1, 'b@example.test')", other)
    await run_draft(draft.ctx, djob, other, mode="draft")
    assert await draft.job(djob) == ("error", "forbidden")
    assert await draft.status(pid) == ("planning", None)


async def test_a_planner_error_ends_the_job_without_a_retry(
    draft: Draft, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_a: object, **_k: object) -> object:
        raise PlanError("cut_cap_unreachable")

    monkeypatch.setattr("saveclock.services.draft.plans.build", broken)
    pid, djob = await draft.analysed()
    await run_draft(draft.ctx, djob, OWNER, mode="draft")  # returns: Dramatiq would not retry
    assert await draft.status(pid) == ("failed_plan", "plan_failed")
    assert await draft.job(djob) == ("error", "internal_error")


async def test_a_planner_error_in_a_replan_keeps_the_stored_plan(
    draft: Draft, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_a: object, **_k: object) -> object:
        raise PlanError("cut_cap_unreachable")

    pid = await draft.drafted()
    r = await draft.client.patch(
        f"/api/v1/projects/{pid}/plan",
        json={"base_version": 1, "ops": [{"op": "set_keywords", "keywords": ["red"]}]},
    )
    monkeypatch.setattr("saveclock.services.draft.plans.build", broken)
    await run_draft(draft.ctx, UUID(r.json()["job_id"]), OWNER, mode="replan")
    assert await draft.status(pid) == ("draft_ready", "plan_failed")
    assert len(await draft.sql("SELECT 1 FROM edit_plans")) == 1


async def _flags(draft: Draft, pid: UUID) -> dict[str, object]:
    flags: dict[str, object] = json.loads(
        (await draft.sql("SELECT flags FROM projects WHERE id = $1", pid))[0][0]
    )
    return flags


async def test_a_song_too_short_for_the_length_flags_the_shorter_draft(draft: Draft) -> None:
    pid = await draft.drafted(seconds=20.0, duration=30)
    plan = await draft.plan(pid)
    flags = await _flags(draft, pid)
    assert flags["length_reduced"] == {"requested_s": 30, "drafted_s": plan.total_frames // 30}
    assert plan.total_frames < 900
    assert {"pool_exhausted", "degraded_keywords"} <= flags.keys()  # written with it, not instead


async def test_a_song_that_fits_the_length_writes_no_notice(draft: Draft) -> None:
    pid = await draft.drafted()  # 30 s asked, 30 s song: the plan is 900 frames
    assert "length_reduced" not in await _flags(draft, pid)


async def test_a_replan_leaves_the_length_notice_as_it_was(draft: Draft) -> None:
    pid = await draft.drafted(seconds=20.0, duration=30)
    before = (await _flags(draft, pid))["length_reduced"]
    r = await draft.client.patch(
        f"/api/v1/projects/{pid}/plan",
        json={"base_version": 1, "ops": [{"op": "set_keywords", "keywords": ["red"]}]},
    )
    await run_draft(draft.ctx, UUID(r.json()["job_id"]), OWNER, mode="replan")
    assert (await _flags(draft, pid))["length_reduced"] == before
