"""Id generation: UUIDv7 (time-ordered) for rows and request ids."""

from uuid import UUID

import uuid_utils


def new_id() -> UUID:
    return UUID(str(uuid_utils.uuid7()))


def new_request_id() -> str:
    return str(new_id())
