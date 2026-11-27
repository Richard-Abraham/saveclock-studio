"""Write the JSON Schema of each `saveclock` command's `--json` output (plan 009).

usage: export_cli_schema.py [output-dir]
       (default: packages/contracts/schemas; files: saveclock-<command>.v1.schema.json)

Sorted keys and a trailing newline: the output is deterministic, so `make contracts-check` can
diff it. Never edit the generated files by hand.
"""

import json
import sys
from pathlib import Path

from saveclock.cli.schema import OUTPUTS

DEFAULT = Path(__file__).resolve().parent.parent / "packages" / "contracts" / "schemas"


def main(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for command, model in OUTPUTS.items():
        text = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        (target / f"saveclock-{command}.v1.schema.json").write_text(text)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))
