"""Printing: stable JSON (sorted keys) or a short human line, and the error exit."""

import json
import sys
from typing import Any

from pydantic import BaseModel

from saveclock.cli.client import CliError


def emit(obj: BaseModel | None, text: str, *, as_json: bool) -> None:
    """`obj` is the command's output model (printed when `--json`), `text` the human form."""
    if as_json and obj is not None:
        print(json.dumps(obj.model_dump(mode="json"), sort_keys=True, indent=2))
    else:
        print(text)


def note(text: str, *, as_json: bool) -> None:
    """Progress for a human, on stderr; silent with `--json` so stdout stays one JSON document."""
    if not as_json:
        print(text, file=sys.stderr, flush=True)


def fail(err: CliError, *, as_json: bool) -> int:
    body: dict[str, Any] = {
        "schema_version": "1",
        "error": {
            "code": err.code,
            "message": err.message,
            "request_id": err.request_id,
            "details": err.details,
        },
    }
    if as_json:
        print(json.dumps(body, sort_keys=True, indent=2))
    else:
        extra = (
            f" ({', '.join(f'{k}={v}' for k, v in sorted(err.details.items()))})"
            if err.details
            else ""
        )
        print(f"error: {err.code}: {err.message}{extra}", file=sys.stderr)
    return err.exit_code
