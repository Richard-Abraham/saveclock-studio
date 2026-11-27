"""Compose files may only publish loopback ports and may not weaken the sandbox (SEC-013/165)."""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOOPBACK_ENV = {"127.0.0.1", "::1", "localhost"}
PORT_OK = (
    # the only two patterns: the port numbers are variables so the restore scratch stack can run beside
    re.compile(r"\$\{BIND_ADDR:-127\.0\.0\.1\}:\$\{API_PORT:-8000\}:8000"),
    re.compile(r"\$\{BIND_ADDR:-127\.0\.0\.1\}:\$\{WEB_PORT:-3000\}:3000"),
    re.compile(r"127\.0\.0\.1:\d+:\d+"),
)
# libraries read these directly and choke on an empty value: the launcher sets them, never compose
THREAD_VARS = {"OMP_NUM_THREADS", "MKL_NUM_THREADS"}
SHELLS = {"sh", "bash", "zsh", "dash"}
EXPECTED = {
    "compose.yml": {"postgres", "redis", "migrate", "api", "web", "worker", "worker-maint"},
    "compose.test.yml": {"postgres", "redis"},
}


def lint(path: Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text()
    doc = yaml.safe_load(text)
    services: dict[str, dict] = doc.get("services", {})
    if "0.0.0.0" in text:  # noqa: S104
        problems.append("0.0.0.0 appears in the file")
    expected = EXPECTED.get(path.name)
    if expected is not None:
        names = set(services)
        for name in sorted(expected - names):
            problems.append(f"missing service {name}")
        for name in sorted(names - expected):
            problems.append(f"unexpected service {name}")
    for name, svc in services.items():
        for port in svc.get("ports", []) or []:
            if not isinstance(port, str) or not any(p.fullmatch(port) for p in PORT_OK):
                problems.append(f"{name}: port {port!r} is not loopback-bound")
        if path.name == "compose.yml" and name not in {"api", "web"} and svc.get("ports"):
            problems.append(f"{name}: must not publish ports")
        labels = svc.get("labels") or {}
        label_keys = labels if isinstance(labels, list) else list(labels)
        for label in label_keys:
            if str(label).startswith("traefik."):
                problems.append(f"{name}: traefik label {label}")
        if "tailscale" in name or "tailscale" in str(svc.get("image", "")):
            problems.append(f"{name}: tailscale is not part of the local-only edition")
        if svc.get("network_mode") == "host":
            problems.append(f"{name}: network_mode host")
        if svc.get("privileged") is True:
            problems.append(f"{name}: privileged")
        if path.name == "compose.yml" and name == "worker":
            scratch = [t for t in svc.get("tmpfs", []) or [] if str(t).startswith("/scratch:")]
            if not scratch or "noexec" not in scratch[0]:
                problems.append("worker: /scratch tmpfs with noexec is missing")
        if path.name == "compose.yml" and name == "worker-maint" and "/scratch" in text.split(
            "worker-maint:", 1
        )[1].split("\n  ", 1)[0]:
            problems.append("worker-maint: must not get a /scratch (it never decodes)")
        if path.name == "compose.yml":
            nets = svc.get("networks") or []
            nets = list(nets) if isinstance(nets, list | dict) else []
            if "egress" in nets and name != "worker":
                problems.append(f"{name}: only the worker may join the egress network")
            if name == "worker" and "egress" not in nets:
                problems.append("worker: must join the egress network (stock search, keywords)")
            keys = [k for k in (svc.get("environment") or {}) if str(k).endswith("_API_KEY")]
            if keys and name != "worker":
                problems.append(f"{name}: provider keys may only reach the worker ({keys})")
        for key in THREAD_VARS & set(svc.get("environment") or {}):
            problems.append(f"{name}: {key} is set by the launcher, never by compose")
        command = svc.get("command")
        if name in {"worker", "worker-maint"} and isinstance(command, list):
            if command and str(command[0]).split("/")[-1] in SHELLS:
                problems.append(f"{name}: the command must be the launcher list, not a shell")
        for volume in svc.get("volumes", []) or []:
            source = volume if isinstance(volume, str) else str(volume.get("source", ""))
            if "docker.sock" in source or "podman.sock" in source:
                problems.append(f"{name}: container socket mounted ({source})")
    return problems


def env_problems() -> list[str]:
    env = ROOT / ".env"
    if not env.is_file():
        return []
    for line in env.read_text().splitlines():
        if line.startswith("BIND_ADDR="):
            value = line.split("=", 1)[1].strip().strip("\"'")
            if value not in LOOPBACK_ENV:
                return [f".env: BIND_ADDR={value} is not loopback"]
    return []


def main() -> int:
    problems = env_problems()
    for path in sorted((ROOT / "infra" / "compose").glob("*.yml")):
        problems += [f"{path.name}: {p}" for p in lint(path)]
    for p in problems:
        print(f"COMPOSE LINT {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
