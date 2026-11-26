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
case "$1" in
  inspect) echo "536870912 100000" ;;
  ps) echo fakeid ;;
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
[ "$fail" = 0 ] && { echo "SANDBOX SCRIPT TEST PASSED"; exit 0; }
exit 1
