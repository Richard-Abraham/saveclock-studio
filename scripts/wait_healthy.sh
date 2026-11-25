#!/usr/bin/env bash
# wait_healthy.sh <compose-project> [timeout_s]: block until every container of the project is healthy.
set -eu
project="$1"; timeout="${2:-90}"
CONTAINER="${CONTAINER:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}"
end=$((SECONDS + timeout))
while [ "$SECONDS" -lt "$end" ]; do
  names="$($CONTAINER ps -a --filter "label=io.podman.compose.project=$project" --filter "label=com.docker.compose.project=$project" --format '{{.Names}}' 2>/dev/null || true)"
  if [ -z "$names" ]; then
    names="$($CONTAINER ps -a --filter "label=io.podman.compose.project=$project" --format '{{.Names}}' 2>/dev/null || true)"
  fi
  if [ -z "$names" ]; then
    names="$($CONTAINER ps -a --filter "label=com.docker.compose.project=$project" --format '{{.Names}}' 2>/dev/null || true)"
  fi
  ok=1
  [ -n "$names" ] || ok=0
  for n in $names; do
    [ "$($CONTAINER inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$n")" = "healthy" ] || ok=0
  done
  [ "$ok" = 1 ] && { echo "healthy: $(echo $names)"; exit 0; }
  sleep 2
done
echo "timeout waiting for $project" >&2
exit 1
