#!/usr/bin/env bash
# make sandbox: verify the hardening on the RUNNING containers (T-1.16, SEC-013/131/133/165).
# Never trusts the compose file: podman-compose ignores some keys silently.
# env: COMPOSE (the compose command incl. -p/-f), CONTAINER (docker|podman)
set -u
: "${COMPOSE:?}"; : "${CONTAINER:?}"
fail=0
pass() { echo "PASS $1"; }
bad() { echo "FAIL $1"; fail=1; }

in_svc() { # service, command...: run inside the container
  local svc="$1"; shift
  # shellcheck disable=SC2086
  $COMPOSE exec -T "$svc" "$@"
}
chk() { # label, service, sh-snippet that must exit 0
  if in_svc "$2" sh -c "$3" >/dev/null 2>&1; then pass "$2: $1"; else bad "$2: $1"; return 1; fi
}

# service:memory-bytes:cpu-quota
for spec in api:536870912:100000 worker:4294967296:300000 worker-maint:268435456:100000; do
  IFS=: read -r svc mem quota <<<"$spec"
  chk "uid is 10001" "$svc" '[ "$(id -u)" = 10001 ]'
  # CapEff is 0 for any non-root user, so it cannot prove cap_drop: the bounding set (CapBnd) can.
  chk "no capabilities (CapEff and CapBnd 0)" "$svc" 'grep -q "^CapEff:[[:space:]]*0000000000000000$" /proc/self/status && grep -q "^CapBnd:[[:space:]]*0000000000000000$" /proc/self/status'
  chk "no-new-privileges" "$svc" 'grep -q "^NoNewPrivs:[[:space:]]*1$" /proc/self/status'
  # uid 10001 cannot write to / anyway, so a failed touch proves nothing: read the mount flags.
  chk "root filesystem is mounted read-only" "$svc" 'awk '"'"'$5=="/" {print $6}'"'"' /proc/self/mountinfo | grep -qE "^ro(,|$)"'
  chk "/data/blobs is writable" "$svc" 'touch /data/blobs/.sandbox && rm /data/blobs/.sandbox'
  chk "/tmp is writable" "$svc" 'touch /tmp/.sandbox && rm /tmp/.sandbox'
  chk "no container socket" "$svc" '[ ! -e /var/run/docker.sock ] && [ ! -e /run/podman/podman.sock ]'
  chk "seccomp filter active" "$svc" 'grep -q "^Seccomp:[[:space:]]*2$" /proc/self/status'
  chk "memory.max = $mem" "$svc" "[ \"\$(cat /sys/fs/cgroup/memory.max)\" = $mem ]" && mem_enforced=1 || mem_enforced=0
  chk "cpu.max quota = $quota" "$svc" "[ \"\$(cut -d' ' -f1 /sys/fs/cgroup/cpu.max)\" = $quota ]"
  # a hog that touches 2x the limit must be OOM-killed (exit 137) quickly, but never run it
  # when the limit is not enforced: it would eat the host's RAM
  if [ "$mem_enforced" != 1 ]; then echo "SKIP $svc: memory limit not enforced"; continue; fi
  start=$SECONDS
  # shellcheck disable=SC2016
  in_svc "$svc" python -c "
n = $mem * 2
b = bytearray(n)
for i in range(0, n, 4096):
    b[i] = 1
" >/dev/null 2>&1
  rc=$?
  if [ "$rc" = 137 ] && [ $((SECONDS - start)) -le 20 ]; then pass "$svc: memory hog OOM-killed (137) in $((SECONDS - start))s"
  else bad "$svc: memory hog exit=$rc after $((SECONDS - start))s (want 137 within 20s)"; fi
done

chk "ffmpeg -version" worker 'ffmpeg -version | head -1'
chk "ffmpeg encodes a synthetic clip" worker 'ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc=duration=1:size=64x64 -f null -'

# host side
cid() { # service -> container id (podman-compose and docker compose both label the service)
  $CONTAINER ps -q --filter "label=com.docker.compose.service=$1" --filter "label=io.podman.compose.project=saveclock" 2>/dev/null | head -1
}
api_ports="$($CONTAINER port "$(cid api)" 2>/dev/null)"
if echo "$api_ports" | grep -q "127.0.0.1:8000" && ! echo "$api_ports" | grep -vq "127.0.0.1:"; then pass "host: api publishes only 127.0.0.1:8000 ($api_ports)"
else bad "host: api ports are '$api_ports'"; fi
for svc in postgres redis worker worker-maint; do
  published="$($CONTAINER port "$(cid "$svc")" 2>/dev/null)"
  if [ -z "$published" ]; then pass "host: $svc publishes nothing"; else bad "host: $svc publishes '$published'"; fi
done
listeners="$(ss -ltnH 2>/dev/null | awk '{print $4}' | grep -E ':(8000|5432|6379)$' || true)"
if [ -n "$listeners" ] && ! echo "$listeners" | grep -qvE '^127\.0\.0\.1:8000$'; then pass "host: ss shows only 127.0.0.1:8000 ($listeners)"
else bad "host: ss listeners: '$listeners'"; fi

lan_ip="$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)"
if [ -z "$lan_ip" ]; then echo "UNAVAILABLE LAN check: no global IPv4 address (second-machine check is in plan 003)"
elif curl -s --max-time 4 -o /dev/null "http://$lan_ip:8000/api/v1/health/live"; then bad "host: http://$lan_ip:8000 answered from the LAN address"
else pass "host: http://$lan_ip:8000 refused on the LAN address"; fi

if [ "$fail" = 0 ]; then echo "SANDBOX OK"; exit 0; fi
echo "SANDBOX FAILED"; exit 1
