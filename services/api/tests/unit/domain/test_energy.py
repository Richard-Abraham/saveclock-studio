import pytest

from saveclock.domain.energy import bar_energy, energy_curve, levels, sections
from saveclock.domain.segment import SegmentTooLong, select_segment

DOWNBEATS = [float(i) for i in range(0, 12, 2)]  # 2 s bars: 0, 2, 4, 6, 8, 10


def test_curve_is_normalised_to_unit_range() -> None:
    curve = energy_curve([-60.0 + i for i in range(101)])
    assert min(curve) == 0.0
    assert max(curve) == 1.0
    assert energy_curve([]) == []
    assert energy_curve([-30.0, -30.0]) == [0.5, 0.5]


def test_bar_energy_averages_the_curve_between_downbeats() -> None:
    curve = [0.2] * 20 + [0.8] * 20  # 10 Hz: 2 s quiet then 2 s loud
    assert bar_energy(curve, [0.0, 2.0, 4.0]) == pytest.approx([0.2, 0.8])


def test_levels_use_fixed_thresholds_and_the_rise_rule() -> None:
    assert levels([0.1, 0.3, 0.6, 0.9]) == ["e1", "e2", "e3", "e4"]
    # 0.2 -> 0.6 rises by 0.4 >= 0.35 and reaches e3: e4
    assert levels([0.2, 0.6]) == ["e1", "e4"]
    # 0.2 -> 0.5 rises by only 0.3: stays e3
    assert levels([0.2, 0.5]) == ["e1", "e3"]


def test_quiet_loud_quiet_gives_three_sections_on_downbeats() -> None:
    bars = [0.2, 0.2, 0.5, 0.5, 0.5, 0.2, 0.2]
    downbeats = [float(2 * i) for i in range(8)]
    out = sections(levels(bars), downbeats)
    assert [s.energy for s in out] == ["e1", "e3", "e1"]
    assert [(s.id, s.start_s, s.end_s) for s in out] == [
        ("s1", 0.0, 4.0),
        ("s2", 4.0, 10.0),
        ("s3", 10.0, 14.0),
    ]
    assert all(s.start_s in downbeats and s.end_s in downbeats for s in out)


def test_short_runs_merge_into_the_neighbour() -> None:
    levs = ["e1", "e1", "e3", "e1", "e1", "e1"]  # a one-bar blip in the middle
    out = sections(levs, [float(i) for i in range(7)])
    assert [(s.energy, s.start_s, s.end_s) for s in out] == [("e1", 0.0, 6.0)]
    first_short = sections(["e3", "e1", "e1", "e1"], [float(i) for i in range(5)])
    assert [(s.energy, s.start_s, s.end_s) for s in first_short] == [("e1", 0.0, 4.0)]


@pytest.mark.parametrize("pattern", [[1, 1, 2, 2, 2, 3, 3, 1, 1, 1], [0, 1, 0, 1, 0, 1, 0, 1]])
def test_every_section_boundary_is_a_downbeat(pattern: list[int]) -> None:
    bars = [p / 3 for p in pattern]
    downbeats = [1.7 * i for i in range(len(bars) + 1)]
    for s in sections(levels(bars), downbeats):
        assert s.start_s in downbeats
        assert s.end_s in downbeats


def test_default_segment_starts_at_the_loudest_window() -> None:
    bars = [0.1] * 4 + [0.9] * 15 + [0.1] * 4  # 2 s bars, loud from 8 s to 38 s
    downbeats = [2.0 * i for i in range(len(bars) + 1)]
    seg = select_segment(bars, downbeats, duration_s=46.0, length_s=30.0)
    assert (seg.start_s, seg.end_s, seg.total_frames) == (8.0, 38.0, 900)


def test_segment_ties_go_to_the_earliest() -> None:
    bars = [0.5] * 10
    downbeats = [2.0 * i for i in range(11)]
    assert select_segment(bars, downbeats, 20.0, 10.0).start_s == 0.0


def test_a_sixty_second_request_on_a_forty_second_song_is_refused() -> None:
    with pytest.raises(SegmentTooLong):
        select_segment([0.5] * 4, [0.0, 10.0, 20.0, 30.0, 40.0], 40.0, 60.0)


def test_no_downbeat_that_fits_starts_at_zero() -> None:
    seg = select_segment([0.5], [30.0, 32.0], 35.0, 15.0)
    assert seg.start_s == 0.0
