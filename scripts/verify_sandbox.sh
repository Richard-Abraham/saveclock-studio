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

cid() { # service -> container id (podman-compose and docker compose both label the service)
  $CONTAINER ps -q --filter "label=com.docker.compose.service=$1" --filter "label=io.podman.compose.project=${PROJECT:-saveclock}" 2>/dev/null | head -1
}
for svc in api web worker worker-maint; do
  # compose owns the limits: read what it actually created, then prove the cgroup enforces them
  read -r mem quota <<<"$($CONTAINER inspect --format '{{.HostConfig.Memory}} {{.HostConfig.CpuQuota}}' "$(cid "$svc")")"
  if [ "${mem:-0}" = 0 ] || [ "${quota:-0}" = 0 ]; then bad "$svc: container has no memory/cpu limit (mem=$mem quota=$quota)"; continue; fi
  chk "uid is 10001" "$svc" '[ "$(id -u)" = 10001 ]'
  # CapEff is 0 for any non-root user, so it cannot prove cap_drop: the bounding set (CapBnd) can.
  chk "no capabilities (CapEff and CapBnd 0)" "$svc" 'grep -q "^CapEff:[[:space:]]*0000000000000000$" /proc/self/status && grep -q "^CapBnd:[[:space:]]*0000000000000000$" /proc/self/status'
  chk "no-new-privileges" "$svc" 'grep -q "^NoNewPrivs:[[:space:]]*1$" /proc/self/status'
  # uid 10001 cannot write to / anyway, so a failed touch proves nothing: read the mount flags.
  chk "root filesystem is mounted read-only" "$svc" 'awk '"'"'$5=="/" {print $6}'"'"' /proc/self/mountinfo | grep -qE "^ro(,|$)"'
  if [ "$svc" = web ]; then  # no blob volume; Next writes its runtime cache to a tmpfs
    chk "/app/apps/web/.next/cache is writable" "$svc" 'touch /app/apps/web/.next/cache/.sandbox && rm /app/apps/web/.next/cache/.sandbox'
  else
    chk "/data/blobs is writable" "$svc" 'touch /data/blobs/.sandbox && rm /data/blobs/.sandbox'
  fi
  chk "/tmp is writable" "$svc" 'touch /tmp/.sandbox && rm /tmp/.sandbox'
  if [ "$svc" = worker ]; then  # decode scratch: a writable tmpfs that cannot execute anything
    chk "/scratch is writable" "$svc" 'touch /scratch/.sandbox && rm /scratch/.sandbox'
    chk "/scratch is mounted noexec" "$svc" 'awk '"'"'$5=="/scratch" {print $6}'"'"' /proc/self/mountinfo | grep -q noexec'
  fi
  chk "no container socket" "$svc" '[ ! -e /var/run/docker.sock ] && [ ! -e /run/podman/podman.sock ]'
  chk "seccomp filter active" "$svc" 'grep -q "^Seccomp:[[:space:]]*2$" /proc/self/status'
  chk "memory.max = $mem" "$svc" "[ \"\$(cat /sys/fs/cgroup/memory.max)\" = $mem ]" && mem_enforced=1 || mem_enforced=0
  chk "cpu.max quota = $quota" "$svc" "[ \"\$(cut -d' ' -f1 /sys/fs/cgroup/cpu.max)\" = $quota ]"
  # a hog that touches 2x the limit must be OOM-killed (exit 137) quickly, but never run it
  # when the limit is not enforced: it would eat the host's RAM
  if [ "$mem_enforced" != 1 ]; then echo "SKIP $svc: memory limit not enforced"; continue; fi
  start=$SECONDS
  if [ "$svc" = web ]; then  # the web image has no python: hold filled 16 MiB buffers until killed
    in_svc "$svc" node -e "const a = []; for (;;) a.push(Buffer.alloc(1 << 24, 1));" >/dev/null 2>&1
  else
    # shellcheck disable=SC2016
    in_svc "$svc" python -c "
n = $mem * 2
b = bytearray(n)
for i in range(0, n, 4096):
    b[i] = 1
" >/dev/null 2>&1
  fi
  rc=$?
  if [ "$rc" = 137 ] && [ $((SECONDS - start)) -le 20 ]; then pass "$svc: memory hog OOM-killed (137) in $((SECONDS - start))s"
  else bad "$svc: memory hog exit=$rc after $((SECONDS - start))s (want 137 within 20s)"; fi
done

chk "ffmpeg -version" worker 'ffmpeg -version | head -1'
chk "ffmpeg encodes a synthetic clip" worker 'ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc=duration=1:size=64x64 -f null -'

# host side
api_ports="$($CONTAINER port "$(cid api)" 2>/dev/null)"
if echo "$api_ports" | grep -q "127.0.0.1:8000" && ! echo "$api_ports" | grep -vq "127.0.0.1:"; then pass "host: api publishes only 127.0.0.1:8000 ($api_ports)"
else bad "host: api ports are '$api_ports'"; fi
web_ports="$($CONTAINER port "$(cid web)" 2>/dev/null)"
if echo "$web_ports" | grep -q "127.0.0.1:3000" && ! echo "$web_ports" | grep -vq "127.0.0.1:"; then pass "host: web publishes only 127.0.0.1:3000 ($web_ports)"
else bad "host: web ports are '$web_ports'"; fi
for svc in postgres redis worker worker-maint; do
  published="$($CONTAINER port "$(cid "$svc")" 2>/dev/null)"
  if [ -z "$published" ]; then pass "host: $svc publishes nothing"; else bad "host: $svc publishes '$published'"; fi
done
listeners="$(ss -ltnH 2>/dev/null | awk '{print $4}' | grep -E ':(3000|8000|5432|6379)$' | sort || true)"
if echo "$listeners" | grep -qx '127.0.0.1:8000' && echo "$listeners" | grep -qx '127.0.0.1:3000' && ! echo "$listeners" | grep -qvE '^127\.0\.0\.1:(3000|8000)$'; then pass "host: ss shows only 127.0.0.1:3000 and :8000 ($(echo $listeners))"
else bad "host: ss listeners: '$(echo $listeners)'"; fi

lan_ip="$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)"
if [ -z "$lan_ip" ]; then echo "UNAVAILABLE LAN check: no global IPv4 address (second-machine check is in plan 003)"
else
  for port in 8000 3000; do
    if curl -s --max-time 4 -o /dev/null "http://$lan_ip:$port/"; then bad "host: http://$lan_ip:$port answered from the LAN address"
    else pass "host: http://$lan_ip:$port refused on the LAN address"; fi
  done
fi

if [ "$fail" = 0 ]; then echo "SANDBOX OK"; exit 0; fi
echo "SANDBOX FAILED"; exit 1
