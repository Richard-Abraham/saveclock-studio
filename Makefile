SHELL := /bin/bash
.DEFAULT_GOAL := help
# compose project name; override to keep a second checkout's volumes apart (PROJECT=saveclock-x make dev)
PROJECT ?= saveclock
# host ports (compose reads the same names); the restore proof and the fresh-clone timing use 18000/13000
API_PORT ?= 8000
WEB_PORT ?= 3000
API := services/api
UV := uv --directory $(API)
COMPOSE_BIN := $(shell command -v docker >/dev/null 2>&1 && echo "docker compose" || echo "podman compose")
CONTAINER := $(shell command -v docker >/dev/null 2>&1 && echo docker || echo podman)
COMPOSE = $(COMPOSE_BIN) -p $(PROJECT) --env-file .env -f infra/compose/compose.yml
COMPOSE_TEST = $(COMPOSE_BIN) -p saveclock-test -f infra/compose/compose.test.yml
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
# value of a variable in .env (empty when absent): the one source of the web image's public origins
envval = $(shell sed -n 's/^$(1)=//p' .env 2>/dev/null | tail -1)
FFMPEG_SRC := $(HOME)/saveclock-spike/downloads/ffmpeg-9.0.x-static
HADOLINT := docker.io/hadolint/hadolint@sha256:9a3944b7fddcb947d1ffd90829ac1a6e5c30479223358f249d8b96c7d0019e27
TRIVY := ghcr.io/aquasecurity/trivy@sha256:6e7f515a46af13a01d534734c666261de65c6e6fe389fa2309e9e2d07470f3a8

# Stages, in order; the first failure stops the run and names the stage.
FAST_STAGES := guard secrets banned doctor env-docs-check fmt-check lint types arch pins \
  compose-lint test-deps-up ffmpeg-bin test migrations web-install contracts-check audit \
  web-env web-lint web-test web-build bundle-scan web-audit-prod
CHECK_STAGES := $(FAST_STAGES) images image-guards hadolint

.PHONY: help guard secrets banned doctor fmt-check lint types arch pins compose-lint test \
  migrations audit env env-docs env-docs-check contracts contracts-check test-deps-up \
  test-deps-down ffmpeg-cache ffmpeg-bin models-cache test-ml fake-stock images image-guards hadolint scan-images up dev down \
  down-volumes sandbox check-fast check web-install web-env web-lint web-test web-build \
  bundle-scan web-audit-prod measure-rewrite smoke-web web-audit stack-up seed smoke-stub \
  predeploy-scan backup backup-init backup-test restore-proof backup-install-timer backup-timer-uninstall rollback-demo fresh-clone-timing

help:
	@echo "targets: check-fast check dev down sandbox images scan-images env env-docs contracts"

guard:
	scripts/check-config-malware.sh --deep .

secrets:
	gitleaks dir . --no-banner --redact --exit-code 1
	@if [ -n "$$(git ls-files '.env*' | grep -v '^.env.example$$')" ]; then \
	  echo "a .env file is tracked"; exit 1; fi

banned:
	python3 scripts/check_banned_deps.py

doctor:
	scripts/check_toolchain.sh

env-docs:
	$(UV) run python ../../scripts/gen_env_docs.py

env-docs-check: env-docs
	git diff --exit-code .env.example infra/ENV.md

env:
	scripts/gen_env.sh

fmt-check:
	$(UV) run ruff format --check .

lint:
	$(UV) run ruff check .

types:
	$(UV) run mypy

arch:
	$(UV) run lint-imports

pins:
	python3 scripts/check_pins.py

compose-lint:
	$(UV) run python ../../scripts/lint_compose.py

test-deps-up:
	$(COMPOSE_TEST) up -d
	CONTAINER=$(CONTAINER) scripts/wait_healthy.sh saveclock-test 90

test-deps-down:
	$(COMPOSE_TEST) down

test:
	$(UV) run pytest -q -m "not golden and not live and not ml and not migration_roundtrip" --cov --cov-branch \
	  --cov-report=json:coverage.json --cov-fail-under=85
	python3 scripts/cov_floors.py

# the real Beat This model on a generated click track; needs the worker's ml extra and the weights
test-ml:
	MODELS_DIR="$(CURDIR)/infra/docker/cache/models" $(UV) run --extra ml pytest -q -m ml

# the 8 generated stock clips FAKE_STOCK serves (never committed; plan 005)
fake-stock: ffmpeg-bin
	$(UV) run python ../../eval/scripts/make_fake_stock.py ../../.data/fake-stock

# alembic check (models == migration) and a downgrade -1 / upgrade head round trip
migrations:
	$(UV) run pytest -q -m migration_roundtrip

# openapi.json from the Python models, then the TS types from openapi.json (T-1.4a)
contracts:
	$(UV) run python ../../scripts/export_openapi.py
	$(UV) run python ../../scripts/export_edit_plan_schema.py
	pnpm --filter @saveclock/contracts generate

# Regenerates into a temp dir and compares with the checked-in files, so a hand edit of either
# file, a stale regeneration and an un-regenerated Python change all fail (and nothing is overwritten).
contracts-check: guard
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	$(UV) run python ../../scripts/export_openapi.py "$$tmp/openapi.json"; \
	pnpm --filter @saveclock/contracts exec openapi-typescript "$$tmp/openapi.json" -o "$$tmp/schema.d.ts" >/dev/null; \
	diff -u packages/contracts/openapi.json "$$tmp/openapi.json" || { echo "CONTRACT DRIFT: openapi.json differs from the Python models (run make contracts)"; exit 1; }; \
	$(UV) run python ../../scripts/export_edit_plan_schema.py "$$tmp/edit-plan.v1.schema.json"; \
	diff -u packages/contracts/schemas/edit-plan.v1.schema.json "$$tmp/edit-plan.v1.schema.json" || { echo "CONTRACT DRIFT: edit-plan.v1.schema.json differs from the Python model (run make contracts)"; exit 1; }; \
	diff -u packages/contracts/src/schema.d.ts "$$tmp/schema.d.ts" || { echo "CONTRACT DRIFT: schema.d.ts differs from openapi.json (run make contracts)"; exit 1; }; \
	echo "contracts in sync"

audit:
	scripts/audit.sh

# --- images (T-1.11, T-1.17) -------------------------------------------------------------
ffmpeg-cache:
	@pin_sha=$$(sed -n 's/^SHA256=//p' infra/docker/ffmpeg.pin); \
	name=$$(sed -n 's|^URL=.*/||p' infra/docker/ffmpeg.pin); \
	if echo "$$pin_sha  infra/docker/cache/$$name" | sha256sum -c - >/dev/null 2>&1; then echo "OK (cached copy verified)"; exit 0; fi; \
	echo "$$pin_sha  $(FFMPEG_SRC)/$$name" | sha256sum -c - || { echo "REFUSING: source tarball does not match the pin"; exit 1; }; \
	cp "$(FFMPEG_SRC)/$$name" infra/docker/cache/ && \
	echo "$$pin_sha  infra/docker/cache/$$name" | sha256sum -c - && echo OK

# the pinned FFmpeg for host tests (the Fedora build has no libx264): extracted to .data/ffmpeg
ffmpeg-bin: ffmpeg-cache
	python3 infra/docker/fetch_ffmpeg.py infra/docker/ffmpeg.pin infra/docker/cache .data/ffmpeg

# the Beat This weights from the owner's local download, sha256-checked against the manifest
# and the SigLIP 2 snapshot from the owner's one-time download at the pinned revision (plan 005)
MODELS_SRC := $(HOME)/saveclock-spike/downloads/models-beat_this
SIGLIP_SRC := $(HOME)/saveclock-downloads/siglip2
models-cache:
	python3 scripts/fetch_models.py infra/docker/models.manifest.json $(MODELS_SRC) infra/docker/cache/models none
	python3 scripts/fetch_models.py infra/docker/models.manifest.json $(SIGLIP_SRC) infra/docker/cache/models siglip2-base-patch16-224

images: ffmpeg-cache models-cache
	$(CONTAINER) build --target api -f infra/docker/Dockerfile.api \
	  --build-arg APP_VERSION=sha-$(GIT_SHA) -t saveclock-api:sha-$(GIT_SHA) -t saveclock-api:local .
	$(CONTAINER) build --target worker -f infra/docker/Dockerfile.api \
	  --build-arg APP_VERSION=sha-$(GIT_SHA) -t saveclock-worker:sha-$(GIT_SHA) -t saveclock-worker:local .
	$(CONTAINER) build --target web -f infra/docker/Dockerfile.web \
	  --build-arg NEXT_PUBLIC_APP_ORIGIN=$(call envval,APP_ORIGIN) \
	  --build-arg NEXT_PUBLIC_API_ORIGIN=$(call envval,NEXT_PUBLIC_API_ORIGIN) \
	  -t saveclock-web:sha-$(GIT_SHA) -t saveclock-web:local .

image-guards:
	CONTAINER=$(CONTAINER) scripts/check_image_contents.sh saveclock-api:sha-$(GIT_SHA) api
	CONTAINER=$(CONTAINER) scripts/check_image_contents.sh saveclock-worker:sha-$(GIT_SHA) worker
	EXPECT_APP_ORIGIN=$(call envval,APP_ORIGIN) EXPECT_API_ORIGIN=$(call envval,NEXT_PUBLIC_API_ORIGIN) \
	  CONTAINER=$(CONTAINER) scripts/check_image_contents.sh saveclock-web:sha-$(GIT_SHA) web
	@echo "IMAGE GUARDS OK"

hadolint:
	$(CONTAINER) run --rm -i $(HADOLINT) hadolint - < infra/docker/Dockerfile.api
	$(CONTAINER) run --rm -i $(HADOLINT) hadolint - < infra/docker/Dockerfile.web

# Not part of `check` (needs the vulnerability DB download). Triage the report in the change summary (SEC-092).
scan-images:
	mkdir -p .data
	$(CONTAINER) save -o .data/saveclock-api.tar saveclock-api:sha-$(GIT_SHA)
	$(CONTAINER) save -o .data/saveclock-worker.tar saveclock-worker:sha-$(GIT_SHA)
	for t in api worker; do \
	  $(CONTAINER) run --rm -v "$(CURDIR)/.data:/scan:ro,z" $(TRIVY) image --input /scan/saveclock-$$t.tar \
	    --severity HIGH,CRITICAL --exit-code 0 || exit 1; \
	done

# --- the stack (T-1.10) ------------------------------------------------------------------
up:
	scripts/sync_env_flags.sh
	$(MAKE) images
	$(MAKE) stack-up

# the compose half of `up` (no image build): the rollback demo runs it with IMAGE_TAG=<tag>
stack-up:
	$(COMPOSE) up -d postgres redis
	CONTAINER=$(CONTAINER) scripts/wait_healthy.sh $(PROJECT) 120
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d

dev: up
	@for i in $$(seq 1 60); do \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$(API_PORT)/api/v1/health/ready); \
	  [ "$$code" = 200 ] && { echo "ready: $$code"; exit 0; }; sleep 2; done; \
	echo "api did not become ready"; exit 1
	@for i in $$(seq 1 60); do \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$(WEB_PORT)/healthz); \
	  [ "$$code" = 200 ] && { echo "web ready: $$code"; exit 0; }; sleep 2; done; \
	echo "web did not become ready"; exit 1

down:
	$(COMPOSE) down

down-volumes:
	@[ "$(CONFIRM)" = yes ] || { echo "this deletes the saveclock volumes (database, blobs): re-run with CONFIRM=yes"; exit 1; }
	$(COMPOSE) down -v

sandbox:
	PROJECT=$(PROJECT) COMPOSE="$(COMPOSE)" CONTAINER=$(CONTAINER) scripts/verify_sandbox.sh

# --- the web shell (T-1.7, plan 002) ------------------------------------------------------
# Every target that runs node tooling depends on `guard` (the config-malware check) first.
web-install: guard
	pnpm install --frozen-lockfile

web-env:
	scripts/check_web_env.sh

web-lint: guard
	pnpm exec prettier --check apps packages
	pnpm --filter @saveclock/web lint
	pnpm --filter @saveclock/web typecheck
	pnpm --filter @saveclock/contracts exec tsc --noEmit

web-test: guard
	pnpm --filter @saveclock/web test

web-build: guard
	pnpm --filter @saveclock/web build

bundle-scan:
	scripts/scan_bundle.sh

# Offline is a failure, not a silent skip; ALLOW_OFFLINE=1 accepts it on purpose. NPM_REGISTRY is
# overridable so the offline path can be exercised.
NPM_REGISTRY ?= https://registry.npmjs.org/
web-audit-prod: guard
	@if ! curl -sfI --max-time 8 $(NPM_REGISTRY) >/dev/null 2>&1; then \
	  if [ "$(ALLOW_OFFLINE)" = 1 ]; then echo "SKIPPED (offline, ALLOW_OFFLINE=1): pnpm audit needs the network"; \
	  else echo "pnpm audit needs the network; set ALLOW_OFFLINE=1 to skip it on purpose"; exit 1; fi; \
	else pnpm audit --prod; fi

# stack-dependent (run after `make dev`); plan 003's bring-up runs them too. smoke-web covers the
# response headers as well (it absorbed the old web-headers check).
measure-rewrite:
	PROJECT=$(PROJECT) python3 scripts/measure_rewrite.py --container $(CONTAINER)

smoke-web:
	python3 scripts/smoke_web.py

# Lighthouse is an exact-pinned devDependency of apps/web (in the lockfile), run with `pnpm exec`.
web-audit: guard
	@chrome=$$(command -v google-chrome chromium chromium-browser | head -1); \
	[ -n "$$chrome" ] || { echo "NOT MEASURED (no Chrome): run this on a machine with Chrome"; exit 1; }; \
	rm -rf .data/lighthouse && mkdir -p .data/lighthouse; \
	for u in / /settings; do curl -s -o /dev/null http://localhost:3000$$u; done; \
	for page in home:/ settings:/settings; do \
	  CHROME_PATH="$$chrome" pnpm --filter @saveclock/web exec lighthouse "http://localhost:3000$${page#*:}" --quiet \
	    --output=json --output-path="$(CURDIR)/.data/lighthouse/$${page%%:*}.json" \
	    --chrome-flags="--headless=new --no-sandbox" || exit 1; \
	done; \
	python3 scripts/check_lighthouse.py .data/lighthouse

# --- bring-up, backup, restore, rollback (plan 003) --------------------------------------
# These need the running stack. PROJECT=<name> picks the compose project; API_PORT/WEB_PORT the ports.
STACK_ENV = PROJECT=$(PROJECT) CONTAINER=$(CONTAINER) COMPOSE="$(COMPOSE)" API_PORT=$(API_PORT) WEB_PORT=$(WEB_PORT)

seed:
	python3 scripts/smoke_stub.py --seed --web http://localhost:$(WEB_PORT) --api http://127.0.0.1:$(API_PORT)

smoke-stub:
	COMPOSE="$(COMPOSE)" python3 scripts/smoke_stub.py --web http://localhost:$(WEB_PORT) \
	  --api http://127.0.0.1:$(API_PORT)

predeploy-scan:
	scripts/predeploy_scan.sh .

backup:
	$(STACK_ENV) bash infra/backup/backup.sh

# first run on a new backup folder: creates the (empty) restic repository, nothing else
backup-init:
	$(STACK_ENV) BACKUP_INIT=1 bash infra/backup/backup.sh

backup-test:
	$(STACK_ENV) bash infra/backup/test_backup.sh

restore-proof:
	$(STACK_ENV) bash infra/backup/restore_proof.sh

# Writes to ~/.config/systemd/user and enables the timer: run it on the machine that should back up.
backup-install-timer:
	@mkdir -p $(HOME)/.config/systemd/user
	@for u in saveclock-backup.service saveclock-backup.timer; do \
	  sed -e 's|@REPO@|$(CURDIR)|' -e 's|@PROJECT@|$(PROJECT)|' infra/backup/systemd/$$u > $(HOME)/.config/systemd/user/$$u; done
	systemctl --user daemon-reload
	systemctl --user enable --now saveclock-backup.timer
	systemctl --user list-timers saveclock-backup.timer --no-pager

backup-timer-uninstall:
	-systemctl --user disable --now saveclock-backup.timer
	rm -f $(HOME)/.config/systemd/user/saveclock-backup.service $(HOME)/.config/systemd/user/saveclock-backup.timer
	systemctl --user daemon-reload

rollback-demo:
	$(STACK_ENV) bash scripts/rollback_demo.sh

fresh-clone-timing:
	PROJECT=$(PROJECT) CONTAINER=$(CONTAINER) bash scripts/fresh_clone_timing.sh

# --- gates -------------------------------------------------------------------------------
# run_stages <stage...>: one runner for both gates; stops at the first failure and names it.
define run_stages
@set -e; trap '$(MAKE) --no-print-directory test-deps-down >/dev/null 2>&1' EXIT; \
for s in $(1); do \
  echo "==> stage $$s"; \
  $(MAKE) --no-print-directory $$s || { echo "FAILED stage: $$s"; exit 2; }; \
done; echo $(2)
endef

check-fast:
	$(call run_stages,$(FAST_STAGES),CHECK-FAST OK)

check:
	$(call run_stages,$(CHECK_STAGES),CHECK OK)
