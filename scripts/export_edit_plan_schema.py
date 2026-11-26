"""Write the edit-plan JSON Schema (the same Pydantic model as the API's plan response).

usage: export_edit_plan_schema.py [output-path]
       (default: packages/contracts/schemas/edit-plan.v1.schema.json)

Sorted keys and a trailing newline: the output is deterministic, so `make contracts-check` can
diff it. Never edit the generated file by hand.
"""

import json
import sys
from pathlib import Path

from saveclock.domain.edit_plan import EditPlan

DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "contracts"
    / "schemas"
    / "edit-plan.v1.schema.json"
)


def schema_text() -> str:
    return json.dumps(EditPlan.model_json_schema(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(schema_text())
