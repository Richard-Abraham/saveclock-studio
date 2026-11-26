"""GET and PATCH /projects/{id}/plan over HTTP with a real draft behind them."""

import json
from typing import Any
from uuid import UUID

import pytest

from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.plan_validator import blocking, validate_plan
from saveclock.services.draft import run_draft
from tests.integration.draft_harness import OWNER, Draft

pytestmark = pytest.mark.integration


async def get_plan(d: Draft, pid: UUID, version: int | None = None) -> Any:
    query = f"?version={version}" if version else ""
    return await d.client.get(f"/api/v1/projects/{pid}/plan{query}")


async def patch(d: Draft, pid: UUID, base: int, *ops: dict[str, Any]) -> Any:
    return await d.client.patch(
        f"/api/v1/projects/{pid}/plan", json={"base_version": base, "ops": list(ops)}
    )


async def test_get_before_any_plan_is_a_conflict_with_a_reason(draft: Draft) -> None:
    pid, _ = await draft.analysed()
    r = await get_plan(draft, pid)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"
    assert r.json()["error"]["details"]["reason"] == "no_plan_yet"


async def test_get_after_the_draft_and_an_absent_version(draft: Draft) -> None:
    pid = await draft.drafted()
    r = await get_plan(draft, pid)
    assert r.status_code == 200
    body = r.json()
    assert (body["version"], body["frozen"], body["total_frames"]) == (1, False, 900)
    plan = EditPlan.model_validate({k: v for k, v in body.items() if k != "frozen"})
    assert blocking(validate_plan(plan, allow_repeats=True, beats_s=plan.beat_grid.beats_s)) == []
    assert (await get_plan(draft, pid, 1)).status_code == 200
    assert (await get_plan(draft, pid, 2)).status_code == 404
    summary = (await draft.client.get(f"/api/v1/projects/{pid}")).json()["plan"]
    assert summary == {
        "version": 1,
        "frozen": False,
        "total_frames": 900,
        "n_cuts": len(body["cuts"]),
        "keyword_source": "table",
    }


async def test_a_stale_base_version_is_a_conflict_with_the_current_version(draft: Draft) -> None:
    pid = await draft.drafted()
    r = await patch(draft, pid, 7, {"op": "set_density", "level": 1})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "plan_version_conflict"
    assert r.json()["error"]["details"] == {"current_version": 1}
    assert (await draft.plan(pid)).options.density == 0  # nothing was applied


async def test_set_density_replaces_the_working_version_in_place(draft: Draft) -> None:
    pid = await draft.drafted()
    before = await draft.plan(pid)
    r = await patch(draft, pid, 1, {"op": "set_density", "level": -2})
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["version"] == 1
    assert after["options"]["density"] == -2
    assert len(after["cuts"]) < len(before.cuts)
    assert after["created_by"] == "user"
    assert [v[0] for v in await draft.sql("SELECT version FROM edit_plans")] == [1]
    assert after["content_hash"] != before.content_hash


async def test_an_identical_patch_writes_nothing(draft: Draft) -> None:
    pid = await draft.drafted()
    first = await patch(draft, pid, 1, {"op": "set_density", "level": 1})
    stamp = (await draft.sql("SELECT updated_at FROM edit_plans"))[0][0]
    second = await patch(draft, pid, 1, {"op": "set_density", "level": 1})
    assert second.status_code == 200
    assert second.json()["content_hash"] == first.json()["content_hash"]
    assert (await draft.sql("SELECT updated_at FROM edit_plans"))[0][0] == stamp


async def test_a_frozen_version_is_never_edited(draft: Draft) -> None:
    pid = await draft.drafted()
    frozen_hash = (await draft.plan(pid)).content_hash
    await draft.freeze(pid)
    r = await patch(draft, pid, 1, {"op": "set_density", "level": -2})
    assert r.status_code == 200
    assert (r.json()["version"], r.json()["frozen"]) == (2, False)
    assert (await draft.plan(pid, 1)).content_hash == frozen_hash
    assert (await draft.plan(pid, 1)).options.density == 0
    assert (await get_plan(draft, pid, 1)).json()["frozen"] is True


async def test_a_patch_on_a_ready_project_returns_it_to_draft_ready(draft: Draft) -> None:
    pid = await draft.drafted()
    await draft.sql("UPDATE projects SET status = 'ready' WHERE id = $1", pid)
    assert (await patch(draft, pid, 1, {"op": "set_density", "level": 1})).status_code == 200
    assert await draft.status(pid) == ("draft_ready", None)


async def test_a_patch_while_planning_is_a_conflict(draft: Draft) -> None:
    pid = await draft.drafted()
    await draft.sql("UPDATE projects SET status = 'planning' WHERE id = $1", pid)
    r = await patch(draft, pid, 1, {"op": "set_density", "level": 1})
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "wrong_state"


async def test_tempo_ops_change_the_grid_and_come_back(draft: Draft) -> None:
    pid = await draft.drafted()
    half = (await patch(draft, pid, 1, {"op": "set_tempo_octave", "octave": -1})).json()
    assert half["beat_grid"]["tempo_octave_adjust"] == -1
    assert half["beat_grid"]["tempo_bpm"] == pytest.approx(64.0, abs=1)
    typed = (await patch(draft, pid, 1, {"op": "set_bpm", "bpm": 100})).json()
    assert typed["beat_grid"]["source"] == "bpm:100"
    assert typed["beat_grid"]["fallback"] == "even_grid"
    back = (await patch(draft, pid, 1, {"op": "use_detected_beats", "on": True})).json()
    assert back["beat_grid"]["source"].startswith("fake_click_picker")
    even = (await patch(draft, pid, 1, {"op": "set_bpm", "use_even_grid": True})).json()
    assert even["beat_grid"]["source"] == "even_grid"
    bad = await patch(draft, pid, 1, {"op": "use_detected_beats", "on": False})
    assert bad.status_code == 422
    assert bad.json()["error"]["details"]["reason"] == "no_fallback_grid"


async def test_set_segment_snaps_to_a_downbeat_and_refuses_the_impossible(draft: Draft) -> None:
    pid = await draft.drafted(seconds=60.0)
    ok = await patch(draft, pid, 1, {"op": "set_segment", "start_s": 7.1, "duration_s": 15})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["total_frames"] == 450
    assert body["segment"]["start_s"] in body["beat_grid"]["downbeats_s"]
    assert abs(body["segment"]["start_s"] - 7.1) < 2.0
    assert body["audio"]["trim"]["start_s"] == body["segment"]["start_s"]
    assert body["audio"]["trim"]["duration_frames"] == 450
    auto = await patch(draft, pid, 1, {"op": "set_segment", "auto": True, "duration_s": 30})
    assert auto.status_code == 200
    for op in (
        {"op": "set_segment", "start_s": 58.0, "duration_s": 30},
        {"op": "set_segment", "start_s": 1.0, "duration_s": 45},
    ):
        r = await patch(draft, pid, 1, op)
        assert r.status_code == 422
        assert r.json()["error"]["details"]["reason"] == "segment_out_of_range"


async def test_lock_clip_is_a_flag_only_and_survives_a_density_change(draft: Draft) -> None:
    pid = await draft.drafted()
    before = await draft.plan(pid)
    r = await patch(draft, pid, 1, {"op": "lock_clip", "cut_index": 0, "locked": True})
    assert r.status_code == 200
    locked = r.json()
    assert locked["cuts"][0]["clip"]["locked"] is True
    assert [c["out_start_frame"] for c in locked["cuts"]] == [
        c.out_start_frame for c in before.cuts
    ]
    assert [c["clip"]["provider_id"] for c in locked["cuts"]] == [
        c.clip.provider_id for c in before.cuts
    ]
    more = await patch(draft, pid, 1, {"op": "set_density", "level": 1})  # denser: cut 0 stays
    assert more.status_code == 200
    assert more.json()["cuts"][0]["clip"]["provider_id"] == before.cuts[0].clip.provider_id
    assert more.json()["cuts"][0]["clip"]["locked"] is True
    gone = await patch(draft, pid, 1, {"op": "set_segment", "start_s": 4.0, "duration_s": 15})
    assert gone.status_code == 409
    assert gone.json()["error"]["code"] == "lock_conflict"
    assert gone.json()["error"]["details"]["reason"] == "lock_boundary_missing"
    assert (await draft.plan(pid)).cuts[0].clip.locked is True  # the plan is unchanged
    bad = await patch(draft, pid, 1, {"op": "lock_clip", "cut_index": 999, "locked": True})
    assert bad.status_code == 422
    assert bad.json()["error"]["details"]["reason"] == "no_such_cut"


async def test_a_batch_is_all_or_nothing(draft: Draft) -> None:
    pid = await draft.drafted()
    before = await draft.plan(pid)
    r = await patch(
        draft,
        pid,
        1,
        {"op": "set_density", "level": -2},
        {"op": "set_segment", "start_s": 500.0, "duration_s": 30},
    )
    assert r.status_code == 422
    assert (await draft.plan(pid)).content_hash == before.content_hash


async def test_bad_bodies_are_validation_errors(draft: Draft) -> None:
    pid = await draft.drafted()
    for body in (
        {"base_version": 1, "ops": []},
        {"base_version": 1, "ops": [{"op": "swap_clip", "cut_index": 0}]},  # a Phase 3 op
        {"base_version": 1, "ops": [{"op": "set_density", "level": 5}]},
        {"base_version": 1, "ops": [{"op": "set_density", "level": 0, "x": 1}]},
        {"base_version": 0, "ops": [{"op": "set_density", "level": 0}]},
        {"ops": [{"op": "set_density", "level": 0}]},
    ):
        r = await draft.client.patch(f"/api/v1/projects/{pid}/plan", json=body)
        assert r.status_code == 422, body
        assert r.json()["error"]["code"] == "validation_error"


async def test_set_keywords_starts_a_replan_job(draft: Draft) -> None:
    pid = await draft.drafted()
    r = await patch(draft, pid, 1, {"op": "set_keywords", "keywords": ["red", "green"]})
    assert r.status_code == 202, r.text
    job_id = UUID(r.json()["job_id"])
    assert await draft.status(pid) == ("planning", None)
    stage = (await draft.sql("SELECT stage, queue, state FROM jobs WHERE id = $1", job_id))[0]
    assert tuple(stage) == ("replan", "fetch", "queued")
    assert draft.env.enqueuer.sent[-1][0] == "replan"
    again = await patch(draft, pid, 1, {"op": "set_keywords", "keywords": ["blue"]})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "conflict"
    opts = json.loads((await draft.sql("SELECT options FROM projects WHERE id = $1", pid))[0][0])
    assert opts["keywords_override"] == ["red", "green"]


async def test_set_keywords_is_refused_while_a_render_runs_or_beside_other_ops(
    draft: Draft,
) -> None:
    pid = await draft.drafted()
    mixed = await patch(
        draft,
        pid,
        1,
        {"op": "set_keywords", "keywords": ["red"]},
        {"op": "set_density", "level": 1},
    )
    assert mixed.status_code == 422
    assert mixed.json()["error"]["details"]["reason"] == "mixed_ops_not_supported"
    for extra, reason in (
        ({"section_id": "s1"}, "section_keywords_not_supported"),
        ({"vibe_chips": ["calm"]}, "vibe_chips_not_supported"),
    ):
        r = await patch(draft, pid, 1, {"op": "set_keywords", "keywords": ["red"], **extra})
        assert (r.status_code, r.json()["error"]["details"]["reason"]) == (422, reason)
    await draft.sql("UPDATE projects SET status = 'rendering' WHERE id = $1", pid)
    busy = await patch(draft, pid, 1, {"op": "set_keywords", "keywords": ["red"]})
    assert busy.status_code == 409
    assert busy.json()["error"]["details"]["reason"] == "render_active"
    local = await patch(draft, pid, 1, {"op": "set_density", "level": 1})  # P6-11: always allowed
    assert local.status_code == 200
    assert await draft.status(pid) == ("rendering", None)  # a render's project stays rendering


async def test_an_active_job_makes_set_keywords_a_conflict(draft: Draft) -> None:
    pid = await draft.drafted()
    await draft.sql(
        "INSERT INTO jobs (id, project_id, stage, queue, state)"
        " VALUES (gen_random_uuid(), $1, 'replan', 'fetch', 'running')",
        pid,
    )
    r = await patch(draft, pid, 1, {"op": "set_keywords", "keywords": ["red"]})
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "job_active"
    assert await draft.status(pid) == ("draft_ready", None)  # rolled back whole


async def test_the_replan_job_keeps_a_locked_cut_and_bumps_a_frozen_version(draft: Draft) -> None:
    pid = await draft.drafted()
    locked_clip = (await draft.plan(pid)).cuts[0].clip.provider_id
    assert (
        await patch(draft, pid, 1, {"op": "lock_clip", "cut_index": 0, "locked": True})
    ).status_code == 200
    r = await patch(draft, pid, 1, {"op": "set_keywords", "keywords": ["red", "blue"]})
    assert r.status_code == 202
    await run_draft(draft.ctx, UUID(r.json()["job_id"]), OWNER, mode="replan")
    assert await draft.status(pid) == ("draft_ready", None)
    plan = await draft.plan(pid)
    assert plan.version == 1  # the working version was replaced in place
    assert plan.options.keywords_override == ["red", "blue"]
    assert plan.provenance.keyword_source == "explicit"
    assert plan.cuts[0].clip.provider_id == locked_clip
    assert plan.cuts[0].clip.locked is True
    await draft.freeze(pid)
    again = await patch(draft, pid, 1, {"op": "set_keywords", "keywords": ["green"]})
    await run_draft(draft.ctx, UUID(again.json()["job_id"]), OWNER, mode="replan")
    assert (await draft.plan(pid)).version == 2
    assert (await draft.plan(pid, 1)).options.keywords_override == ["red", "blue"]


async def test_a_replan_that_cannot_keep_a_lock_leaves_the_plan_alone(draft: Draft) -> None:
    pid = await draft.drafted()
    before = await draft.plan(pid)
    await patch(draft, pid, 1, {"op": "lock_clip", "cut_index": 1, "locked": True})
    locked = await draft.plan(pid)
    # the owner's clip no longer fits its cut (as if the cut had grown): the replan must refuse
    rows = await draft.sql("SELECT id, plan FROM edit_plans")
    data = json.loads(rows[0][1])
    data["cuts"][1]["clip"]["mezzanine_frames"] = 1
    await draft.sql(
        "UPDATE edit_plans SET plan = $1::jsonb WHERE id = $2", json.dumps(data), rows[0][0]
    )
    r = await patch(draft, pid, 1, {"op": "set_keywords", "keywords": ["red"]})
    await run_draft(draft.ctx, UUID(r.json()["job_id"]), OWNER, mode="replan")
    assert await draft.status(pid) == ("draft_ready", "lock_conflict")
    assert (await draft.job(UUID(r.json()["job_id"])))[1] == "lock_conflict"
    assert before.cuts[0].out_end_frame == locked.cuts[0].out_end_frame
    assert (
        json.loads((await draft.sql("SELECT plan FROM edit_plans"))[0][0])["cuts"][1]["clip"][
            "mezzanine_frames"
        ]
        == 1
    )


async def test_a_second_user_gets_404_for_get_and_patch(draft: Draft) -> None:
    pid = await draft.drafted()
    other = UUID("00000000-0000-4000-8000-0000000000bb")
    await draft.sql("INSERT INTO users (id, email) VALUES ($1, 'b@example.test')", other)
    await draft.sql("UPDATE projects SET user_id = $1 WHERE id = $2", other, pid)
    assert (await get_plan(draft, pid)).status_code == 404
    assert (await patch(draft, pid, 1, {"op": "set_density", "level": 1})).status_code == 404


async def test_a_foreign_origin_is_refused(draft: Draft) -> None:
    pid = await draft.drafted()
    r = await draft.client.patch(
        f"/api/v1/projects/{pid}/plan",
        json={"base_version": 1, "ops": [{"op": "set_density", "level": 1}]},
        headers={"origin": "http://evil.example"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["details"]["reason"] == "origin_mismatch"
