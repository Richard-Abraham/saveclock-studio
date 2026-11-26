#!/usr/bin/env bash
# Regression test for verify_sandbox.sh: when a memory limit is not enforced, the memory hog
# must NOT run (it would eat the host's RAM) and the run must fail.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cat >"$tmp/fakecompose" <<'EOF'
#!/usr/bin/env bash
# fakecompose exec -T <svc> sh -c <snippet> | python -c <code>
if [ "$4" = python ]; then touch "$MARKER"; exit 0; fi
case "$6" in *memory.max*) exit 1 ;; esac   # the limit is not enforced
exit 0
EOF
cat >"$tmp/fakecontainer" <<'EOF'
#!/usr/bin/env bash
# ps prints "id-<service>" (read from the label filter); inspect prints limits, or the networks
# of that id from NETS_<service> (underscores for dashes)
case "$1" in
  inspect)
    case "$3" in
      *NetworkSettings*) var="NETS_$(echo "${4#id-}" | tr - _)"; echo "${!var:-}" ;;
      *) echo "536870912 100000" ;;
    esac ;;
  ps) for a in "$@"; do case "$a" in label=com.docker.compose.service=*) echo "id-${a##*service=}" ;; esac; done ;;
esac
exit 0
EOF
chmod +x "$tmp/fakecompose" "$tmp/fakecontainer"

out="$(MARKER="$tmp/hog-ran" COMPOSE="$tmp/fakecompose" CONTAINER="$tmp/fakecontainer" "$here/verify_sandbox.sh" 2>&1)"
rc=$?
fail=0
[ ! -e "$tmp/hog-ran" ] || { echo "FAIL memory hog ran although the limit was not enforced"; fail=1; }
echo "$out" | grep -q "^SKIP api: memory limit not enforced" || { echo "FAIL no SKIP line for api"; fail=1; }
[ "$rc" != 0 ] || { echo "FAIL sandbox run did not fail"; fail=1; }

# plan 005: the expected network sets pass, a planted second network on worker-maint fails
run_nets() { # NETS_worker_maint value
  NETS_worker="saveclock_back saveclock_egress" NETS_worker_maint="$1" NETS_postgres="saveclock_back" \
    NETS_redis="saveclock_back" MARKER="$tmp/hog2" COMPOSE="$tmp/fakecompose" CONTAINER="$tmp/fakecontainer" \
    "$here/verify_sandbox.sh" 2>&1
}
expected="$(run_nets "saveclock_back")"
echo "$expected" | grep -q "^PASS networks: worker is on 'back egress'" || { echo "FAIL worker networks not accepted"; fail=1; }
echo "$expected" | grep -q "^PASS networks: worker-maint is on 'back'" || { echo "FAIL worker-maint network not accepted"; fail=1; }
planted="$(run_nets "saveclock_back saveclock_egress")"
echo "$planted" | grep -q "^FAIL networks: worker-maint is on 'back egress'" || { echo "FAIL planted egress on worker-maint not caught"; fail=1; }
[ "$fail" = 0 ] && { echo "SANDBOX SCRIPT TEST PASSED"; exit 0; }
exit 1
