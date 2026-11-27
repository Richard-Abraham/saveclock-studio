import csv
import io
import json

from saveclock.domain import cutlist
from saveclock.domain import edit_plan as ep
from tests.unit.domain.plan_support import plan


def sample() -> ep.EditPlan:
    return plan(128.0, "e4", seconds=15).plan


def with_attribution(p: ep.EditPlan, index: int, attribution: ep.Attribution) -> ep.EditPlan:
    cuts = list(p.cuts)
    cuts[index] = cuts[index].model_copy(
        update={"clip": cuts[index].clip.model_copy(update={"attribution": attribution})}
    )
    return p.model_copy(update={"cuts": cuts})


def test_the_128_bpm_literal_times_come_from_the_integer_frames() -> None:
    rows = cutlist.cutlist_rows(sample())
    assert [r["start_frame"] for r in rows[:4]] == [0, 28, 56, 84]  # 2 beats of 14.0625 frames
    assert [r["start_s"] for r in rows[:3]] == [0.0, 0.933333, 1.866667]
    assert rows[0]["end_frame"] == rows[1]["start_frame"]
    assert rows[0]["end_s"] == rows[1]["start_s"]
    assert [r["index"] for r in rows] == list(range(len(rows)))


def test_the_kind_and_beat_index_come_from_the_beat_ref() -> None:
    p = sample()
    rows = cutlist.cutlist_rows(p)
    assert {r["kind"] for r in rows} == {"downbeat", "beat"}  # a plan mixing both
    for row, cut in zip(rows, p.cuts, strict=True):
        assert (row["kind"], row["beat_index"]) == (cut.beat_ref.kind, cut.beat_ref.beat_index)


def test_the_json_has_no_audio_and_no_song_hash() -> None:
    p = sample()
    text = cutlist.to_json(p)
    assert "audio" not in text
    assert "sha256" not in text
    assert p.song.sha256 not in text
    doc = json.loads(text)
    assert (doc["fps"], doc["total_frames"]) == (30, p.total_frames)
    assert doc["cuts"][0]["attribution"]["page_url"] == p.cuts[0].clip.attribution.page_url


def test_json_round_trips_to_the_rows() -> None:
    p = sample()
    assert json.loads(cutlist.to_json(p))["cuts"] == cutlist.cutlist_rows(p)


def test_csv_is_rfc4180_quoted_with_crlf() -> None:
    text = cutlist.to_csv(sample())
    assert text.endswith("\r\n")
    assert text.split("\r\n")[0] == ",".join(f'"{c}"' for c in cutlist.COLUMNS)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows[1]["start_s"] == "0.933333"
    assert rows[1]["start_frame"] == "28"
    assert rows[0]["attribution"] == "A (https://p/" + rows[0]["attribution"].split("/")[-1]


def test_a_cell_that_starts_like_a_formula_is_neutralised() -> None:
    evil = "=cmd|' /C calc'!A0"
    p = with_attribution(
        sample(), 0, ep.Attribution(author=evil, author_url=None, page_url="https://p/0")
    )
    rows = list(csv.DictReader(io.StringIO(cutlist.to_csv(p))))
    assert rows[0]["attribution"].startswith("'=cmd")
    for lead in "+-@\t\r\n":
        q = with_attribution(
            sample(), 0, ep.Attribution(author=lead + "x", author_url=None, page_url="https://p/0")
        )
        cell = next(csv.DictReader(io.StringIO(cutlist.to_csv(q))))["attribution"]
        assert cell[0] == "'"


def test_a_null_author_is_null_in_json_and_just_the_page_in_csv() -> None:
    p = with_attribution(
        sample(), 1, ep.Attribution(author=None, author_url=None, page_url="https://p/solo")
    )
    assert json.loads(cutlist.to_json(p))["cuts"][1]["attribution"]["author"] is None
    cell = list(csv.DictReader(io.StringIO(cutlist.to_csv(p))))[1]["attribution"]
    assert cell == "https://p/solo"
    assert "None" not in cell
    assert "()" not in cell
