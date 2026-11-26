#!/usr/bin/env bash
# wait_healthy.sh <compose-project> [timeout_s]: block until every container of the project is healthy.
set -eu
project="$1"; timeout="${2:-90}"
CONTAINER="${CONTAINER:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}"
end=$((SECONDS + timeout))
while [ "$SECONDS" -lt "$end" ]; do
  names=""
  for label in io.podman.compose.project com.docker.compose.project; do  # podman-compose | docker compose
    names="$names $($CONTAINER ps -a --filter "label=$label=$project" --format '{{.Names}}' 2>/dev/null || true)"
  done
  names="$(echo $names | tr " " "\n" | sort -u)"
  ok=1
  [ -n "$names" ] || ok=0
  for n in $names; do
    status="$($CONTAINER inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$n")"
    # containers without a healthcheck (one-shot jobs such as migrate) do not block the wait
    [ "$status" = "healthy" ] || [ "$status" = "none" ] || ok=0
  done
  [ "$ok" = 1 ] && { echo "healthy: $(echo $names)"; exit 0; }
  sleep 2
done
echo "timeout waiting for $project" >&2
exit 1
