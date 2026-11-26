"""Container healthcheck: exit 0 when Redis answers PING."""

import sys

from redis import Redis

from saveclock.config import Settings


def main() -> int:
    settings = Settings()
    try:
        ok = Redis.from_url(
            settings.redis_url.get_secret_value(), socket_connect_timeout=3, socket_timeout=3
        ).ping()
    except Exception:
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
