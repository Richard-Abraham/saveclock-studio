"""make smoke-driver: the dev-only driver page is absent with the flag off and served with it on.

usage: smoke_driver.py --web http://localhost:3000     (env COMPOSE = the compose command, from make)

Recreates only the `web` container: first with DEV_DRIVER empty (expects 404 on /dev), then with
DEV_DRIVER=1 (expects 200), and always puts the flag back off. Never touches data or other services.
"""

import argparse
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request


def status(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 - the caller's own localhost
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return 0


def recreate_web(compose: list[str], flag: str) -> None:
    env = {**os.environ, "DEV_DRIVER": flag}
    subprocess.run(  # noqa: S603 - the compose command make passes, fixed arguments
        [*compose, "up", "-d", "--no-deps", "--force-recreate", "web"],
        env=env, check=True, capture_output=True, timeout=300,
    )  # fmt: skip


def wait_ready(web: str) -> None:
    for _ in range(60):
        if status(f"{web}/healthz") == 200:  # noqa: PLR2004
            return
        time.sleep(2)
    msg = "web did not become ready"
    raise RuntimeError(msg)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://localhost:3000")
    args = parser.parse_args()
    compose = shlex.split(os.environ["COMPOSE"])
    results: dict[str, int] = {}
    try:
        for label, flag in (("off", ""), ("on", "1")):
            recreate_web(compose, flag)
            wait_ready(args.web)
            results[label] = status(f"{args.web}/dev")
    finally:
        recreate_web(compose, "")  # the flag goes back off, whatever happened
        wait_ready(args.web)
    if results.get("off") != 404 or results.get("on") != 200:  # noqa: PLR2004
        print(f"DRIVER FAILED (flag off: {results.get('off')}, flag on: {results.get('on')})")
        return 1
    print("DRIVER OK (flag off: 404, flag on: 200)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
