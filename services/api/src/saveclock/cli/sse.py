"""A small server-sent-events reader (no library): `retry:`, comments, multi-line `data:`."""

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    name: str
    data: Any  # the decoded JSON payload (None when it is not JSON)


def parse(lines: Iterable[str]) -> Iterator[Event]:
    """Yield one `Event` per blank-line-terminated block that carries data, and an `Event("ping")`
    for each comment line (a keep-alive), so a caller can check its deadline on a quiet stream."""
    name = "message"
    data: list[str] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if line == "":
            if data:
                yield Event(name, _decode("\n".join(data)))
            name, data = "message", []
        elif line.startswith(":"):
            yield Event("ping", None)  # a comment, e.g. the `: ping` keep-alive
        else:
            field, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if field == "event":
                name = value
            elif field == "data":
                data.append(value)
            # `retry:` and `id:` are ignored: the client reconnects on its own schedule
    if data:  # a stream that ends mid-block still delivers what it had
        yield Event(name, _decode("\n".join(data)))


def _decode(text: str) -> Any:  # noqa: ANN401
    try:
        return json.loads(text)
    except ValueError:
        return None
