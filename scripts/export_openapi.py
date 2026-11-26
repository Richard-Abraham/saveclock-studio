"""Write the OpenAPI document (thin wrapper over saveclock.export).

usage: export_openapi.py [output-path]   (default: packages/contracts/openapi.json)
"""

import sys
from pathlib import Path

from saveclock.export import openapi_json

DEFAULT = Path(__file__).resolve().parent.parent / "packages" / "contracts" / "openapi.json"

if __name__ == "__main__":
    Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT).write_text(openapi_json())
