import random
import struct
from pathlib import Path
from typing import Any

import pytest

from saveclock.domain.ranking import (
    RankedClip,
    diversity,
    near_duplicates,
    rank,
    top_k,
    top_k_count,
)
from saveclock.domain.sampling import (
    clip_score,
    cosine,
    frame_scores,
    mean_vector,
    normalize,
    sample_count,
)
from saveclock.domain.stock_rules import ClipMeta, RejectReason, check_candidate, is_blurry
from saveclock.domain.video_checks import Check, moov_before_mdat, pts_deltas, video_checks
from saveclock.domain.windows import Window, best_window


def meta(**kw: Any) -> ClipMeta:
    base: dict[str, Any] = {"width": 1080, "height": 1920, "duration_s": 10.0}
    return ClipMeta(**{**base, **kw})


@pytest.mark.parametrize(
    ("kw", "reason"),
    [
        ({}, None),
        ({"width": 1920, "height": 1080}, RejectReason.NOT_PORTRAIT),
        ({"width": 1080, "height": 1080}, RejectReason.NOT_PORTRAIT),
        ({"width": 719, "height": 1280}, RejectReason.TOO_SMALL),
        ({"width": 720, "height": 1280}, None),
        ({"fps": 23.9}, RejectReason.LOW_FPS),
        ({"fps": 24.0}, None),
        ({"duration_s": 2.9}, RejectReason.TOO_SHORT),
        ({"duration_s": 3.0}, None),
        ({"duration_s": 60.1}, RejectReason.TOO_LONG),
        ({"size_bytes": 100 * 1024 * 1024}, None),
        ({"size_bytes": 100 * 1024 * 1024 + 1}, RejectReason.TOO_LARGE),
    ],
)
def test_check_candidate(kw: dict[str, Any], reason: RejectReason | None) -> None:
    assert check_candidate(meta(**kw)) == reason


def test_blur_threshold_is_a_strict_lower_bound() -> None:
    assert is_blurry(39.9)
    assert not is_blurry(40.0)


def test_best_window_takes_the_longest_gap_shrunk_by_the_margin_and_capped() -> None:
    w = best_window([4.0, 9.5], 20.0)
    assert w is not None
    assert w.start_s == 9.7
    assert w.frames == 303  # 10.1 s at 30 fps
    capped = best_window([], 40.0)
    assert capped == Window(0.2, 15.0)
    assert capped.frames == 450


def test_best_window_none_when_cuts_every_two_seconds() -> None:
    assert best_window([2.0, 4.0, 6.0], 8.0) is None


def test_best_window_tie_goes_to_the_earliest_and_ignores_cuts_outside() -> None:
    w = best_window([4.0, -1.0, 99.0], 8.0)
    assert w is not None
    assert w.start_s == 0.2
    assert w.frames == 108  # 3.6 s


def test_best_window_first_cut_matters() -> None:
    # without the cut at 8.0 the longer first gap would win; with it the second gap does
    w = best_window([8.0], 20.0)
    assert w is not None
    assert w.start_s == 8.2


def clip(pid: str, score: float, query: str = "q", emb: tuple[float, ...] = ()) -> RankedClip:
    return RankedClip("pexels", pid, query, score, Window(0.2, 3.6), emb)


def test_rank_is_reproducible_and_the_seed_changes_tie_order() -> None:
    ties = [clip(str(i), 0.5) for i in range(12)]
    a = [c.provider_id for c in rank(ties, seed=1)]
    assert a == [c.provider_id for c in rank(list(reversed(ties)), seed=1)]
    assert a != [c.provider_id for c in rank(ties, seed=2)]
    assert [c.provider_id for c in rank([clip("a", 0.1), clip("b", 0.9)], seed=1)] == ["b", "a"]


def test_rank_property_no_duplicate_provider_ids_and_best_score_wins() -> None:
    rng = random.Random(7)  # noqa: S311  # shortcut: a seeded loop instead of the hypothesis library
    for _ in range(200):
        items = [
            clip(str(rng.randrange(8)), rng.random(), query=rng.choice("abc")) for _ in range(30)
        ]
        out = rank(items, seed=rng.randrange(100))
        keys = [(c.provider, c.provider_id) for c in out]
        assert len(keys) == len(set(keys))
        for c in out:
            assert c.score == max(i.score for i in items if i.provider_id == c.provider_id)


def test_top_k_count_and_slice() -> None:
    assert top_k_count(20, 1.3) == 26
    assert top_k_count(10, 1.3) == 13
    assert top_k_count(1, 1.3) == 2
    assert len(top_k([clip(str(i), 1.0 - i / 100) for i in range(40)], 20, 1.3)) == 26
    assert len(top_k([clip("a", 1.0)], 20, 1.3)) == 1


def test_near_duplicates_adjacent_pairs_only() -> None:
    def unit(angle_cos: float) -> tuple[float, ...]:
        return (1.0, 0.0) if angle_cos == 1.0 else (angle_cos, (1 - angle_cos**2) ** 0.5)

    ranked = [
        clip("a", 1.0, emb=unit(1.0)),
        clip("b", 0.9, emb=unit(0.95)),  # cosine 0.95 with a: flagged
        clip("c", 0.8, emb=(0.0, 1.0)),
    ]
    assert near_duplicates(ranked) == [("a", "b")]
    assert near_duplicates([clip("a", 1.0, emb=(1.0, 0.0)), clip("b", 0.9, emb=unit(0.89))]) == []


def test_diversity_counts_distinct_queries() -> None:
    assert diversity([clip("a", 1, "x"), clip("b", 1, "x"), clip("c", 1, "y")]) == 2


def test_sampling_helpers() -> None:
    assert sample_count(Window(0, 3.6)) == 3
    assert sample_count(Window(0, 15.0)) == 8
    assert sample_count(Window(0, 0.5)) == 1
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([0, 0], [1, 1]) == 0.0
    assert normalize([3.0, 4.0]) == pytest.approx([0.6, 0.8])
    assert normalize([0.0, 0.0]) == [0.0, 0.0]
    assert mean_vector([[1.0, 2.0], [3.0, 4.0]]) == (2.0, 3.0)
    assert frame_scores([[1, 0], [0, 1]], [1, 0]) == pytest.approx([1.0, 0.0])
    assert clip_score([0.2, 0.4]) == pytest.approx(0.3)


def probe(nb: int, deltas: int = 1000, tb: str = "1/30000", r: str = "30/1") -> dict[str, Any]:
    v = {
        "codec_type": "video", "codec_name": "h264", "profile": "High", "pix_fmt": "yuv420p",
        "width": 1080, "height": 1920, "sample_aspect_ratio": "1:1", "r_frame_rate": r,
        "avg_frame_rate": r, "time_base": tb, "nb_read_frames": str(nb),
    }  # fmt: skip
    return {
        "streams": [v],
        "format": {"duration": f"{nb / 30:.6f}"},
        "pts": [i * deltas for i in range(nb)],
        "moov_first": True,
    }


def failed(checks: list[Check]) -> list[str]:
    return [c.name for c in checks if not c.ok]


def test_pts_deltas_sorted_for_bframes() -> None:
    assert pts_deltas([2000, 0, 1000, 4000, 3000]) == [1000] * 4


def test_video_checks_clean_and_tolerance() -> None:
    assert failed(video_checks(probe(108), 108)) == []
    assert any("QM-062" in n for n in failed(video_checks(probe(109), 108)))
    assert failed(video_checks(probe(109), 108, tolerance=1)) == []
    assert any("QM-062" in n for n in failed(video_checks(probe(110), 108, tolerance=1)))


def test_video_checks_catch_ntsc_audio_geometry_and_stream_count() -> None:
    assert any(
        "QM-061" in n for n in failed(video_checks(probe(108, deltas=1001, r="30000/1001"), 108))
    )
    p = probe(108)
    p["streams"].append({"codec_type": "audio"})
    assert any("QM-077" in n for n in failed(video_checks(p, 108)))
    p = probe(108)
    p["streams"][0]["width"] = 1080
    p["streams"][0]["height"] = 1080
    assert any("QM-060 H.264" in n for n in failed(video_checks(p, 108)))
    p = probe(108)
    p["moov_first"] = False
    assert any("moov" in n for n in failed(video_checks(p, 108)))
    assert len(video_checks({"streams": [], "format": {}}, 1)) == 1


def box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def test_moov_before_mdat_walks_the_boxes(tmp_path: Path) -> None:
    good, late = tmp_path / "good.mp4", tmp_path / "late.mp4"
    good.write_bytes(box(b"ftyp", b"isom") + box(b"moov", b"x" * 20) + box(b"mdat", b"y" * 9))
    late.write_bytes(box(b"ftyp", b"isom") + box(b"mdat", b"y" * 9) + box(b"moov", b"x"))
    assert moov_before_mdat(good)
    assert not moov_before_mdat(late)


def test_moov_walker_handles_large_size_and_open_ended_boxes(tmp_path: Path) -> None:
    large = struct.pack(">I4sQ", 1, b"free", 16 + 5) + b"z" * 5
    f = tmp_path / "large.mp4"
    f.write_bytes(box(b"ftyp") + large + box(b"moov") + struct.pack(">I4s", 0, b"mdat"))
    assert moov_before_mdat(f)
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    assert not moov_before_mdat(empty)
