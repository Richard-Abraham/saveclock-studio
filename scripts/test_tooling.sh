#!/usr/bin/env bash
# Shell tests of the setup tooling: source guard, make help lint, doctor, rollback, audit export.
# Style copied from scripts/test-check-config-malware.sh. Fixtures live in a tmp dir.
set -u
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
holder=""
trap 'rm -rf "$tmp"; [ -z "$holder" ] || kill "$holder" 2>/dev/null' EXIT
fail=0
# expect <desc> <want_rc> <grep-pattern or -> <cmd...>: exit code, and the combined output must match the pattern
expect() {
  local d="$1" want="$2" pat="$3"; shift 3
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" != "$want" ]; then echo "FAIL $d (rc=$rc want $want)"; fail=1; return; fi
  if [ "$pat" != "-" ] && ! printf '%s\n' "$out" | grep -qE -- "$pat"; then
    echo "FAIL $d (output lacks: $pat)"; fail=1; return
  fi
  echo "ok   $d (rc=$rc)"
}
mkdir -p "$tmp/empty"

# ---- check_sources.py (the FFMPEG_SRC / MODELS_SRC refusals) -----------------------------
CS="python3 scripts/check_sources.py"
printf 'fake ffmpeg bytes' >"$tmp/blob"
sha="$(sha256sum "$tmp/blob" | cut -d' ' -f1)"
printf 'URL=https://example.invalid/dir/fake-ffmpeg.tar.xz\nSHA256=%s\n' "$sha" >"$tmp/pin"
printf 'fake model bytes' >"$tmp/mblob"
msha="$(sha256sum "$tmp/mblob" | cut -d' ' -f1)"
msize="$(wc -c <"$tmp/mblob" | tr -d ' ')"
printf '{"models":[{"name":"m","file":"m.ckpt","bytes":%s,"sha256":"%s"}]}\n' "$msize" "$msha" >"$tmp/manifest"
mkdir -p "$tmp/ffsrc" "$tmp/ffgood" "$tmp/ffbad" "$tmp/msrc" "$tmp/mgood" "$tmp/mbad"
cp "$tmp/blob" "$tmp/ffsrc/fake-ffmpeg.tar.xz"; cp "$tmp/blob" "$tmp/ffgood/fake-ffmpeg.tar.xz"
printf 'X%s' "$(cat "$tmp/blob")" >"$tmp/ffbad/fake-ffmpeg.tar.xz"
cp "$tmp/mblob" "$tmp/msrc/m.ckpt"; cp "$tmp/mblob" "$tmp/mgood/m.ckpt"
printf 'Y%s' "$(cat "$tmp/mblob")" >"$tmp/mbad/m.ckpt"
FF="$CS ffmpeg --pin $tmp/pin"
expect "ffmpeg: unset src, empty cache" 2 'FFMPEG_SRC is not set.*docs/SETUP.md section 2a' $FF --cache "$tmp/empty"
expect "ffmpeg: src is not a folder" 2 'FFMPEG_SRC=/nonexistent/x is not a folder' $FF --cache "$tmp/empty" --src /nonexistent/x
expect "ffmpeg: folder lacks the file" 2 'does not contain fake-ffmpeg.tar.xz' $FF --cache "$tmp/empty" --src "$tmp/empty"
expect "ffmpeg: folder has the file" 10 - $FF --cache "$tmp/empty" --src "$tmp/ffsrc"
expect "ffmpeg: valid cache, unset src" 0 'cached copy verified' $FF --cache "$tmp/ffgood"
expect "ffmpeg: corrupted cache, unset src" 2 'FFMPEG_SRC is not set' $FF --cache "$tmp/ffbad"
expect "ffmpeg: --cached-only on empty cache" 1 'FFMPEG_SRC' $FF --cache "$tmp/empty" --cached-only
MM="$CS models --manifest $tmp/manifest"
expect "models: unset src, empty cache" 2 'MODELS_SRC is not set.*docs/SETUP.md section 2b' $MM --cache "$tmp/empty"
expect "models: src is not a folder" 2 'MODELS_SRC=/nonexistent/x is not a folder' $MM --cache "$tmp/empty" --src /nonexistent/x
expect "models: folder lacks the file" 2 'does not contain m.ckpt' $MM --cache "$tmp/empty" --src "$tmp/empty"
expect "models: folder has the file" 10 - $MM --cache "$tmp/empty" --src "$tmp/msrc"
expect "models: valid cache, unset src" 0 'cached copy verified' $MM --cache "$tmp/mgood"
expect "models: corrupted cache, unset src" 2 'MODELS_SRC is not set' $MM --cache "$tmp/mbad"
expect "models: --cached-only on empty cache" 1 'MODELS_SRC' $MM --cache "$tmp/empty" --cached-only

# ---- check_make_help.py (every public target has a ## description) ------------------------
HL="python3 scripts/check_make_help.py"
printf 'a: ## does a\n\t@true\nb: a ## does b\n\t@true\n' >"$tmp/mk_ok"
printf 'a: ## does a\n\t@true\nb:\n\t@true\n' >"$tmp/mk_missing"
printf 'a: ##\n\t@true\n' >"$tmp/mk_empty_text"
printf 'V := x\nW ?= y\n.PHONY: a\na: ## does a\n\t@true\n' >"$tmp/mk_ignored"
: >"$tmp/mk_none"
expect "help-lint: two described targets" 0 'HELP LINT OK \(2 targets\)' $HL "$tmp/mk_ok"
expect "help-lint: undescribed target is named" 1 'target b \(Makefile line 3\)' $HL "$tmp/mk_missing"
expect "help-lint: empty ## text" 1 'target a ' $HL "$tmp/mk_empty_text"
expect "help-lint: variables and .PHONY are ignored" 0 'HELP LINT OK \(1 targets\)' $HL "$tmp/mk_ignored"
expect "help-lint: empty file" 1 'no targets found' $HL "$tmp/mk_none"
expect "help-lint: the real Makefile" 0 'HELP LINT OK' $HL Makefile
expect "make help lists check" 0 '^  check ' make --no-print-directory help
expect "make help lists rollback" 0 '^  rollback ' make --no-print-directory help

# ---- doctor.sh ----------------------------------------------------------------------------
mkdir -p "$tmp/stub_ok" "$tmp/stub_nocompose"
printf '#!/bin/sh\nexit 0\n' >"$tmp/stub_ok/podman"
printf '#!/bin/sh\n[ "$1 $2" = "compose version" ] && exit 1\nexit 0\n' >"$tmp/stub_nocompose/podman"
chmod +x "$tmp/stub_ok/podman" "$tmp/stub_nocompose/podman"
freeport() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }
AP="$(freeport)"; WP="$(freeport)"
dr() { # dr <stub dir> <api port> [VAR=val...]
  local stub="$1" ap="$2"; shift 2
  env CONTAINER="$stub/podman" COMPOSE_BIN="$stub/podman compose" PROJECT=t API_PORT="$ap" WEB_PORT="$WP" \
    DOCTOR_MIN_DISK_GB=1 "$@" scripts/doctor.sh
}
expect "doctor: all good (cache skipped)" 0 'DOCTOR OK' dr "$tmp/stub_ok" "$AP" DOCTOR_SKIP=cache
expect "doctor: compose missing" 1 'compose' dr "$tmp/stub_nocompose" "$AP" DOCTOR_SKIP=cache
python3 -c 'import socket,sys,time; s=socket.socket(); s.bind(("127.0.0.1", int(sys.argv[1]))); s.listen(); time.sleep(120)' "$AP" &
holder=$!
sleep 1
expect "doctor: port in use" 1 "port $AP is in use" dr "$tmp/stub_ok" "$AP" DOCTOR_SKIP=cache
kill "$holder" 2>/dev/null; holder=""
expect "doctor: too little disk" 1 'GB free' dr "$tmp/stub_ok" "$AP" DOCTOR_SKIP=cache DOCTOR_MIN_DISK_GB=999999
expect "doctor: empty cache names FFMPEG_SRC" 1 'FFMPEG_SRC' dr "$tmp/stub_ok" "$AP" DOCTOR_CACHE_DIR="$tmp/empty"
expect "doctor: no node/pnpm/uv probe" 1 - grep -nE '\b(node|pnpm|uv)\b|nvmrc' scripts/doctor.sh

# ---- make rollback ------------------------------------------------------------------------
# make exits 2 for any failed recipe line, so the refusals are told apart by their message.
mkdir -p "$tmp/rb"
printf '#!/bin/sh\n[ "$1 $2" = "image inspect" ] && case "$3" in saveclock-web:*) exit 1 ;; esac\nexit 0\n' >"$tmp/rb/missing_web"
printf '#!/bin/sh\nexit 0\n' >"$tmp/rb/all_exist"
chmod +x "$tmp/rb/missing_web" "$tmp/rb/all_exist"
RB="make --no-print-directory rollback"
expect "rollback: no TAG" 2 'usage: make rollback TAG=sha-' $RB CONTAINER="$tmp/rb/all_exist"
expect "rollback: TAG=latest" 2 'TAG must look like sha-' $RB TAG=latest CONTAINER="$tmp/rb/all_exist"
expect "rollback: web image missing" 2 'REFUSING: image saveclock-web:sha-abcdef1 does not exist' $RB TAG=sha-abcdef1 CONTAINER="$tmp/rb/missing_web"
expect "rollback: all images exist (dry run)" 0 'IMAGE_TAG=sha-abcdef1.*stack-up' make -n rollback TAG=sha-abcdef1 CONTAINER="$tmp/rb/all_exist"

# ---- audit.sh export (the ml extra is audited, PyTorch local versions are stripped) ---------
AE="$tmp/audit_export"
AUDIT_EXPORT_ONLY=1 scripts/audit.sh >"$AE" 2>&1; arc=$?
expect "audit export: exit 0" 0 - test "$arc" = 0
expect "audit export: torch" 0 - grep -qE '^torch==' "$AE"
expect "audit export: torchaudio" 0 - grep -qE '^torchaudio==' "$AE"
expect "audit export: beat-this" 0 - grep -qE '^beat-this==' "$AE"
expect "audit export: no +cpu" 1 - grep -q '+cpu' "$AE"

[ "$fail" = 0 ] && { echo "ALL TOOLING TESTS PASSED"; exit 0; }
echo "TOOLING TESTS FAILED"; exit 1
