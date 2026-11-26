import json
from pathlib import Path
from typing import Any, get_args
from uuid import uuid4

import pytest
from pydantic import ValidationError

from saveclock.domain import edit_plan as ep
from saveclock.domain.plan_hash import canonical_json, content_hash, with_hash
from saveclock.models import Fallback, PlanCreator
from tests.unit.domain.plan_support import plan

SCHEMA_FILE = (
    Path(__file__).resolve().parents[5] / "packages/contracts/schemas/edit-plan.v1.schema.json"
)


def sample() -> ep.EditPlan:
    return plan(128.0, seconds=15).plan


def dump(p: ep.EditPlan) -> dict[str, Any]:
    return p.model_dump(mode="json")


def test_a_valid_plan_round_trips_through_json() -> None:
    p = sample()
    again = ep.EditPlan.model_validate_json(p.model_dump_json())
    assert again == p
    assert again.schema_version == "1.0"
    assert (again.fps, again.resolution.width, again.resolution.height) == (30, 1080, 1920)


PATHS: list[tuple[str, ...]] = [
    (),
    ("resolution",),
    ("song",),
    ("segment",),
    ("beat_grid",),
    ("options",),
    ("cuts", "0"),
    ("cuts", "0", "beat_ref"),
    ("cuts", "0", "section"),
    ("cuts", "0", "clip"),
    ("cuts", "0", "clip", "attribution"),
    ("audio",),
    ("audio", "trim"),
    ("overlays",),
    ("output",),
    ("provenance",),
]


@pytest.mark.parametrize("path", PATHS, ids=lambda p: ".".join(p) or "root")
def test_an_unknown_field_is_rejected_at_every_level(path: tuple[str, ...]) -> None:
    data = dump(sample())
    node: Any = data
    for part in path:
        node = node[int(part)] if part.isdigit() else node[part]
    node["surprise"] = 1
    with pytest.raises(ValidationError):
        ep.EditPlan.model_validate(data)


def test_the_hash_ignores_key_order_plan_id_creator_and_seed() -> None:
    p = sample()
    reordered = json.loads(json.dumps(dump(p), sort_keys=True))
    assert content_hash(ep.EditPlan.model_validate(reordered)) == content_hash(p)
    other = p.model_copy(
        update={
            "plan_id": uuid4(),
            "created_by": "user",
            "provenance": p.provenance.model_copy(update={"seed": 999}),
        }
    )
    assert canonical_json(other) == canonical_json(p)
    assert content_hash(other) == content_hash(p)
    assert len(content_hash(p)) == 32
    assert with_hash(p).content_hash == content_hash(p).hex()


def test_the_hash_changes_with_one_boundary() -> None:
    p = sample()
    cuts = list(p.cuts)
    cuts[0] = cuts[0].model_copy(update={"out_end_frame": cuts[0].out_end_frame + 1})
    assert content_hash(p.model_copy(update={"cuts": cuts})) != content_hash(p)


def test_floats_are_rounded_to_six_decimals_when_the_model_is_built() -> None:
    data = dump(sample())
    data["song"]["duration_s"] = 1.23456789
    assert ep.EditPlan.model_validate(data).song.duration_s == 1.234568


def test_a_float_frame_is_refused_by_the_model() -> None:
    data = dump(sample())
    data["cuts"][0]["out_end_frame"] = 28.0
    with pytest.raises(ValidationError):
        ep.EditPlan.model_validate(data)


def test_the_literals_mirror_the_model_enums() -> None:
    assert set(get_args(ep.CreatedBy)) == {c.value for c in PlanCreator}
    assert set(get_args(ep.FallbackName)) == {f.value for f in Fallback}


def test_the_schema_file_is_the_model_schema() -> None:
    assert json.loads(SCHEMA_FILE.read_text()) == json.loads(
        json.dumps(ep.EditPlan.model_json_schema(), sort_keys=True)
    )
