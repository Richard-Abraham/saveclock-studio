"""The mezzanine normalizer with the real FFmpeg: 30 diverse inputs, then top-K selection."""

from pathlib import Path

import pytest

from saveclock.adapters.blobstore.blob_keys import mezz_key, raw_key
from saveclock.adapters.ffmpeg import Tools, build_mezz, probe_video
from saveclock.domain.video_checks import video_checks
from saveclock.domain.windows import Window
from saveclock.errors import ClipUnavailable
from saveclock.services.normalize import normalize_one, normalize_topk
from tests.factories.media import make
from tests.integration.footage_harness import OWNER, ColourRanker, Footage

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]

SIZES = [(640, 480), (720, 1280), (1080, 1920), (1920, 1080), (3840, 2160), (1000, 1000)]
RATES = ["24", "25", "30000/1001", "30", "50", "60"]
PIX_FMTS = ["yuv420p", "yuv422p", "yuv444p"]
ROTATED = {7, 19}  # a display-matrix rotation flag on a 1920x1080-ish source
ODD_SAR = {0, 5, 10, 15, 20, 25}
WINDOW = Window(0.0, 2.0)  # 60 frames out of 2.5 s inputs


def source_spec(i: int) -> tuple[int, int, str, str, str]:
    w, h = SIZES[i % 6]
    return w, h, RATES[(i + i // 6) % 6], PIX_FMTS[i % 3], "4/3" if i in ODD_SAR else "1"


def make_source(tools: Tools, tmp: Path, i: int) -> Path:
    w, h, rate, pix, sar = source_spec(i)
    src = make(
        tools,
        tmp / f"in{i:02d}.mp4",
        *("-vf", f"setsar={sar},format={pix}"),
        *("-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-g", "30", "-an"),
        pre=["-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r={rate}:d=2.5"],
    )
    if i in ROTATED:
        return make(
            tools, tmp / f"rot{i:02d}.mp4", "-c", "copy", pre=["-display_rotation", "90"], src=src
        )
    return src


def test_the_inputs_cover_every_property_of_the_spec() -> None:
    specs = [source_spec(i) for i in range(30)]
    assert {s[:2] for s in specs} == set(SIZES)
    assert {s[2] for s in specs} == set(RATES)
    assert {s[3] for s in specs} == set(PIX_FMTS)
    assert {s[4] for s in specs} == {"1", "4/3"}
    assert len(specs) == 30


@pytest.mark.parametrize("i", range(30))
def test_every_input_becomes_a_frame_exact_mezzanine(
    ffmpeg_tools: Tools, tmp_path: Path, i: int
) -> None:
    src = make_source(ffmpeg_tools, tmp_path, i)
    out = tmp_path / "mezz.mp4"
    build_mezz(ffmpeg_tools, src, WINDOW, out)
    probe = probe_video(ffmpeg_tools, out)
    failed = [c for c in video_checks(probe, WINDOW.frames, tolerance=1) if not c.ok]
    assert failed == [], (source_spec(i), failed)
    stream = probe["streams"][0]
    assert (stream["width"], stream["height"]) == (1080, 1920)
    assert stream["profile"] == "High"
    assert stream["pix_fmt"] == "yuv420p"
    assert stream["sample_aspect_ratio"] == "1:1"
    assert stream["r_frame_rate"] == stream["avg_frame_rate"] == "30/1"
    assert stream["time_base"] == "1/30000"
    assert abs(int(stream["nb_read_frames"]) - WINDOW.frames) <= 1


# --- top-K selection on the vetted fake clips -------------------------------------------------


async def ranked_footage(footage: Footage) -> Footage:
    await footage.search(["red"])
    return footage.with_ranker(ColourRanker())


async def test_only_k_clips_are_normalised_and_their_frames_are_the_probed_truth(
    footage: Footage, ffmpeg_tools: Tools
) -> None:
    f = await ranked_footage(footage)
    vetted = await f.vet()
    assert len(vetted.ranked) == 5
    done = await normalize_topk(
        f.deps, user_id=OWNER, project_id=f.pid, ranked=vetted.ranked, cuts=3
    )
    assert len(done) == 4  # ceil(1.3 x 3)
    assert [d.provider_id for d in done] == [c.provider_id for c in vetted.ranked[:4]]
    statuses = {r.provider_id: r.status for r in await f.rows(["ranked", "normalized"])}
    assert sorted(statuses.values()) == ["normalized"] * 4 + ["ranked"]
    assert statuses[vetted.ranked[4].provider_id] == "ranked"  # the rest are not encoded
    for clip in done:
        key = mezz_key(f.pid, "pexels", clip.provider_id)
        assert f.ctx.blobs.exists(key)
        probed = probe_video(ffmpeg_tools, f.ctx.blobs.local_path(key))
        assert int(probed["streams"][0]["nb_read_frames"]) == clip.mezz_frames
        row = await f.by_id(clip.provider_id.removeprefix("fake-"))
        assert row.mezz_frames == clip.mezz_frames
    assert not f.ctx.blobs.exists(mezz_key(f.pid, "pexels", vetted.ranked[4].provider_id))
    assert not f.redis.keys("saveclock:heavy:*")


async def test_an_ffprobe_failure_replaces_the_clip_by_the_next_ranked_one(
    footage: Footage,
) -> None:
    f = await ranked_footage(footage)
    vetted = await f.vet()
    best = vetted.ranked[0]
    f.ctx.blobs.put(  # the top clip's source is corrupted after ranking
        raw_key(f.pid, "pexels", best.provider_id),
        [b"\x00\x00\x00\x18ftypisom" + b"\x00" * 200],
        max_bytes=1 << 20,
    )
    done = await normalize_topk(
        f.deps, user_id=OWNER, project_id=f.pid, ranked=vetted.ranked, cuts=3
    )
    assert len(done) == 4
    assert best.provider_id not in {d.provider_id for d in done}
    assert {d.provider_id for d in done} == {c.provider_id for c in vetted.ranked[1:]}
    row = await f.by_id(best.provider_id.removeprefix("fake-"))
    assert (row.status, row.reject_reason) == ("rejected_quality", "ffprobe_failed")


async def test_fewer_ranked_clips_than_k_normalises_what_exists(footage: Footage) -> None:
    f = await ranked_footage(footage)
    vetted = await f.vet()
    done = await normalize_topk(
        f.deps, user_id=OWNER, project_id=f.pid, ranked=vetted.ranked[:2], cuts=20
    )
    assert len(done) == 2


async def test_lazy_normalize_one_works_from_the_stored_window_and_the_raw_file(
    footage: Footage,
) -> None:
    f = await ranked_footage(footage)
    vetted = await f.vet()
    last = vetted.ranked[-1]
    clip = await normalize_one(
        f.deps, user_id=OWNER, project_id=f.pid, provider="pexels", provider_id=last.provider_id
    )
    assert clip.mezz_frames > 0
    assert (await f.by_id(last.provider_id.removeprefix("fake-"))).status == "normalized"
    assert f.ctx.blobs.exists(mezz_key(f.pid, "pexels", last.provider_id))


async def test_lazy_normalize_one_refuses_what_has_no_window_or_no_source(footage: Footage) -> None:
    f = await ranked_footage(footage)
    with pytest.raises(ClipUnavailable):  # found, never vetted: no stored window
        await normalize_one(
            f.deps,
            user_id=OWNER,
            project_id=f.pid,
            provider="pexels",
            provider_id="fake-red_portrait",
        )
    vetted = await f.vet()
    f.ctx.blobs.delete(raw_key(f.pid, "pexels", vetted.ranked[0].provider_id))
    with pytest.raises(ClipUnavailable):  # the source clip is gone
        await normalize_one(
            f.deps,
            user_id=OWNER,
            project_id=f.pid,
            provider="pexels",
            provider_id=vetted.ranked[0].provider_id,
        )
    f.ctx.blobs.put(  # a corrupt source: the encode fails and the clip is unavailable
        raw_key(f.pid, "pexels", vetted.ranked[1].provider_id),
        [b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64],
        max_bytes=1 << 20,
    )
    with pytest.raises(ClipUnavailable):
        await normalize_one(
            f.deps,
            user_id=OWNER,
            project_id=f.pid,
            provider="pexels",
            provider_id=vetted.ranked[1].provider_id,
        )
