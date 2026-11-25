"""Write packages/contracts/openapi.json (thin wrapper over saveclock.api.export)."""

from pathlib import Path

from saveclock.api.export import openapi_json

OUT = Path(__file__).resolve().parent.parent / "packages" / "contracts" / "openapi.json"

if __name__ == "__main__":
    OUT.write_text(openapi_json())
