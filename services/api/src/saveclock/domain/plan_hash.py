"""The plan's content hash (ARCHITECTURE §5): sha256 over canonical JSON of the plan without
`plan_id`, `created_by`, `provenance.seed` and `content_hash` itself, so two plans that cut the same
way hash the same however they were made."""

import hashlib
import json
from typing import Any

from saveclock.domain.edit_plan import EditPlan

EXCLUDED_TOP = ("plan_id", "created_by", "content_hash")


def _canonical_dict(plan: EditPlan) -> dict[str, Any]:
    data: dict[str, Any] = plan.model_dump(mode="json")
    for key in EXCLUDED_TOP:
        data.pop(key)
    data["provenance"].pop("seed")
    return data


def canonical_json(plan: EditPlan) -> bytes:
    text = json.dumps(
        _canonical_dict(plan), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return text.encode()


def content_hash(plan: EditPlan) -> bytes:
    """32 bytes (the `edit_plans.content_hash` column)."""
    return hashlib.sha256(canonical_json(plan)).digest()


def with_hash(plan: EditPlan) -> EditPlan:
    """The same plan with its `content_hash` field set to the hex of `content_hash(plan)`."""
    return plan.model_copy(update={"content_hash": content_hash(plan).hex()})
