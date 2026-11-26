"""Every external image reference must be pinned by digest; the lockfile must match (T-1.17)."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINNED = re.compile(r"@sha256:[0-9a-f]{64}")
LOCAL_BUILD_PREFIX = "saveclock-"  # saveclock-api|worker: built by compose from Dockerfile.api


def dockerfile_offenders(path: Path) -> list[str]:
    stages: set[str] = set()
    bad = []
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if m := re.match(r"FROM\s+(?:--\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", line, re.IGNORECASE):
            image, stage = m.group(1), m.group(2)
            if image != "scratch" and image not in stages and not PINNED.search(image):
                bad.append(f"{path.name}:{number}: FROM {image}")
            if stage:
                stages.add(stage)
        elif m := re.match(r"COPY\s+.*?--from=(\S+)", line, re.IGNORECASE):
            ref = m.group(1)
            if ref not in stages and not ref.isdigit() and not PINNED.search(ref):
                bad.append(f"{path.name}:{number}: COPY --from={ref}")
    return bad


def compose_offenders(path: Path) -> list[str]:
    bad = []
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        if m := re.match(r"\s*image:\s*(\S+)", raw):
            image = m.group(1).strip("\"'")
            if not image.startswith(LOCAL_BUILD_PREFIX) and not PINNED.search(image):
                bad.append(f"{path.name}:{number}: image {image}")
    return bad


def node_tag_offenders() -> list[str]:
    """The node image tag in Dockerfile.web must be the version in .nvmrc (one pin, two readers)."""
    want = (ROOT / ".nvmrc").read_text().strip()
    text = (ROOT / "infra" / "docker" / "Dockerfile.web").read_text()
    tags = set(re.findall(r"library/node:([0-9.]+)-slim@", text))
    return [f"Dockerfile.web: node image tag {t} != .nvmrc {want}" for t in sorted(tags) if t != want] or (
        [] if tags else ["Dockerfile.web: no node image tag found"]
    )


def restic_pin_offenders() -> list[str]:
    """infra/backup/restic.pin is the one owner of the restic image; it must be a digest."""
    pin = ROOT / "infra" / "backup" / "restic.pin"
    if not pin.is_file():
        return ["infra/backup/restic.pin: missing"]
    image = next((ln[6:] for ln in pin.read_text().splitlines() if ln.startswith("IMAGE=")), "")
    return [] if PINNED.search(image) else [f"infra/backup/restic.pin: IMAGE={image!r} is not a digest"]


def main() -> int:
    offenders: list[str] = node_tag_offenders() + restic_pin_offenders()
    for dockerfile in sorted((ROOT / "infra" / "docker").glob("Dockerfile*")):
        offenders += dockerfile_offenders(dockerfile)
    for compose in sorted((ROOT / "infra" / "compose").glob("*.yml")):
        offenders += compose_offenders(compose)
    for line in offenders:
        print(f"UNPINNED {line}")
    if not (ROOT / "services" / "api" / "uv.lock").is_file():
        print("MISSING services/api/uv.lock")
        offenders.append("uv.lock")
    else:
        lock = subprocess.run(  # noqa: S603 - fixed argument list
            ["uv", "--directory", str(ROOT / "services" / "api"), "lock", "--check"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if lock.returncode != 0:
            print("uv lock --check failed:", (lock.stdout + lock.stderr).strip())
            offenders.append("uv lock")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
