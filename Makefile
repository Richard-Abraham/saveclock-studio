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
# folder holding the FFmpeg tarball; no default (the old laptop passes ~/saveclock-spike/downloads/ffmpeg-9.0.x-static)
FFMPEG_SRC ?=
HADOLINT := docker.io/hadolint/hadolint@sha256:9a3944b7fddcb947d1ffd90829ac1a6e5c30479223358f249d8b96c7d0019e27
TRIVY := ghcr.io/aquasecurity/trivy@sha256:6e7f515a46af13a01d534734c666261de65c6e6fe389fa2309e9e2d07470f3a8

# Stages, in order; the first failure stops the run and names the stage.
FAST_STAGES := guard help-lint tooling-test secrets banned toolchain env-docs-check fmt-check lint types arch pins \
  compose-lint test-deps-up ffmpeg-bin test migrations web-install contracts-check audit \
  web-env web-lint web-test web-build bundle-scan web-audit-prod
CHECK_STAGES := $(FAST_STAGES) images image-guards hadolint

.PHONY: help help-lint tooling-test rollback toolchain doctor-dev guard secrets banned doctor fmt-check lint types arch pins compose-lint test \
  migrations audit env env-docs env-docs-check contracts contracts-check test-deps-up \
  test-deps-down ffmpeg-cache ffmpeg-bin models-cache test-ml images image-guards hadolint scan-images up dev down \
  down-volumes sandbox check-fast check web-install web-env web-lint web-test web-build \
  bundle-scan web-audit-prod measure-rewrite smoke-web web-audit stack-up seed smoke-stub \
  predeploy-scan backup backup-init backup-test restore-proof backup-install-timer backup-timer-uninstall rollback-demo fresh-clone-timing

help: ## list every public target with a one-line description
	@awk 'BEGIN{FS=":.*## "} /^[a-zA-Z0-9_-]+:.*## /{printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

help-lint: ## fail if a public make target lacks a ## description
	python3 scripts/check_make_help.py Makefile

tooling-test: ## run the shell tests of the setup tooling (doctor, source guard, help lint, rollback, audit export)
	bash scripts/test_tooling.sh

guard: ## run the config-malware scan
	scripts/check-config-malware.sh --deep .

secrets: ## scan for committed secrets and tracked .env files
	gitleaks dir . --no-banner --redact --exit-code 1
	@if [ -n "$$(git ls-files '.env*' | grep -v '^.env.example$$')" ]; then \
	  echo "a .env file is tracked"; exit 1; fi

banned: ## fail on banned dependencies
	python3 scripts/check_banned_deps.py

doctor: ## check what is needed to RUN the app (container runtime, tools, ports, disk, cached FFmpeg and models)
	PROJECT=$(PROJECT) CONTAINER=$(CONTAINER) COMPOSE_BIN="$(COMPOSE_BIN)" API_PORT=$(API_PORT) WEB_PORT=$(WEB_PORT) scripts/doctor.sh

toolchain: ## check the pinned dev toolchain (uv, Python, node, pnpm); the check stage
	scripts/check_toolchain.sh

doctor-dev: doctor toolchain ## everything in doctor plus the developer tools make check needs

env-docs: ## regenerate .env.example and infra/ENV.md
	$(UV) run python ../../scripts/gen_env_docs.py

env-docs-check: env-docs ## fail if the generated env docs are stale
	git diff --exit-code .env.example infra/ENV.md

env: ## create .env with random secrets
	scripts/gen_env.sh

fmt-check: ## check Python formatting
	$(UV) run ruff format --check .

lint: ## run ruff
	$(UV) run ruff check .

types: ## run mypy
	$(UV) run mypy

arch: ## check import-layer contracts
	$(UV) run lint-imports

pins: ## check dependency and image pins
	python3 scripts/check_pins.py

compose-lint: ## lint the compose files
	$(UV) run python ../../scripts/lint_compose.py

test-deps-up: ## start the test postgres and redis
	$(COMPOSE_TEST) up -d
	CONTAINER=$(CONTAINER) scripts/wait_healthy.sh saveclock-test 90

test-deps-down: ## stop the test postgres and redis
	$(COMPOSE_TEST) down

test: ## run the unit and integration tests with coverage floors
	$(UV) run pytest -q -m "not golden and not live and not ml and not migration_roundtrip" --cov --cov-branch \
	  --cov-report=json:coverage.json --cov-fail-under=85
	python3 scripts/cov_floors.py

# the real Beat This model on a generated click track; needs the worker's ml extra and the weights
test-ml: ## run the real Beat This test (needs the ml extra and the weights)
	MODELS_DIR="$(CURDIR)/infra/docker/cache/models" $(UV) run --extra ml pytest -q -m ml

# alembic check (models == migration) and a downgrade -1 / upgrade head round trip
migrations: ## check models match migrations and the downgrade round trip
	$(UV) run pytest -q -m migration_roundtrip

# openapi.json from the Python models, then the TS types from openapi.json (T-1.4a)
contracts: ## regenerate openapi.json and the TypeScript types
	$(UV) run python ../../scripts/export_openapi.py
	pnpm --filter @saveclock/contracts generate

# Regenerates into a temp dir and compares with the checked-in files, so a hand edit of either
# file, a stale regeneration and an un-regenerated Python change all fail (and nothing is overwritten).
contracts-check: guard ## fail if the generated contracts are stale
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	$(UV) run python ../../scripts/export_openapi.py "$$tmp/openapi.json"; \
	pnpm --filter @saveclock/contracts exec openapi-typescript "$$tmp/openapi.json" -o "$$tmp/schema.d.ts" >/dev/null; \
	diff -u packages/contracts/openapi.json "$$tmp/openapi.json" || { echo "CONTRACT DRIFT: openapi.json differs from the Python models (run make contracts)"; exit 1; }; \
	diff -u packages/contracts/src/schema.d.ts "$$tmp/schema.d.ts" || { echo "CONTRACT DRIFT: schema.d.ts differs from openapi.json (run make contracts)"; exit 1; }; \
	echo "contracts in sync"

audit: ## audit locked Python dependencies (api and ml extra)
	scripts/audit.sh

# --- images (T-1.11, T-1.17) -------------------------------------------------------------
ffmpeg-cache: ## copy the pinned FFmpeg tarball into infra/docker/cache (needs FFMPEG_SRC=<folder> unless cached)
	@python3 scripts/check_sources.py ffmpeg --src "$(FFMPEG_SRC)"; rc=$$?; \
	[ $$rc = 0 ] && { echo "OK (cached copy verified)"; exit 0; }; [ $$rc = 10 ] || exit $$rc; \
	pin_sha=$$(sed -n 's/^SHA256=//p' infra/docker/ffmpeg.pin); \
	name=$$(sed -n 's|^URL=.*/||p' infra/docker/ffmpeg.pin); \
	(cd "$(FFMPEG_SRC)" && echo "$$pin_sha  $$name" | sha256sum -c -) || { echo "REFUSING: source tarball does not match the pin"; exit 1; }; \
	cp "$(FFMPEG_SRC)/$$name" infra/docker/cache/ && \
	echo "$$pin_sha  infra/docker/cache/$$name" | sha256sum -c - && echo OK

# the pinned FFmpeg for host tests (the Fedora build has no libx264): extracted to .data/ffmpeg
ffmpeg-bin: ffmpeg-cache ## extract the pinned FFmpeg for host tests
	python3 infra/docker/fetch_ffmpeg.py infra/docker/ffmpeg.pin infra/docker/cache .data/ffmpeg

# the Beat This weights from the owner's local download, sha256-checked against the manifest
# folder holding the weights; no default (the old laptop passes ~/saveclock-spike/downloads/models-beat_this)
MODELS_SRC ?=
models-cache: ## copy the Beat This weights into infra/docker/cache/models (needs MODELS_SRC=<folder> unless cached)
	@python3 scripts/check_sources.py models --src "$(MODELS_SRC)"; rc=$$?; \
	[ $$rc = 0 ] && { echo "OK (cached models verified)"; exit 0; }; [ $$rc = 10 ] || exit $$rc; \
	python3 scripts/fetch_models.py infra/docker/models.manifest.json "$(MODELS_SRC)" infra/docker/cache/models

images: ffmpeg-cache models-cache ## build the api, worker and web images
	$(CONTAINER) build --target api -f infra/docker/Dockerfile.api \
	  --build-arg APP_VERSION=sha-$(GIT_SHA) -t saveclock-api:sha-$(GIT_SHA) -t saveclock-api:local .
	$(CONTAINER) build --target worker -f infra/docker/Dockerfile.api \
	  --build-arg APP_VERSION=sha-$(GIT_SHA) -t saveclock-worker:sha-$(GIT_SHA) -t saveclock-worker:local .
	$(CONTAINER) build --target web -f infra/docker/Dockerfile.web \
	  --build-arg NEXT_PUBLIC_APP_ORIGIN=$(call envval,APP_ORIGIN) \
	  --build-arg NEXT_PUBLIC_API_ORIGIN=$(call envval,NEXT_PUBLIC_API_ORIGIN) \
	  -t saveclock-web:sha-$(GIT_SHA) -t saveclock-web:local .

image-guards: ## check the built images' contents
	CONTAINER=$(CONTAINER) scripts/check_image_contents.sh saveclock-api:sha-$(GIT_SHA) api
	CONTAINER=$(CONTAINER) scripts/check_image_contents.sh saveclock-worker:sha-$(GIT_SHA) worker
	EXPECT_APP_ORIGIN=$(call envval,APP_ORIGIN) EXPECT_API_ORIGIN=$(call envval,NEXT_PUBLIC_API_ORIGIN) \
	  CONTAINER=$(CONTAINER) scripts/check_image_contents.sh saveclock-web:sha-$(GIT_SHA) web
	@echo "IMAGE GUARDS OK"

hadolint: ## lint the Dockerfiles
	$(CONTAINER) run --rm -i $(HADOLINT) hadolint - < infra/docker/Dockerfile.api
	$(CONTAINER) run --rm -i $(HADOLINT) hadolint - < infra/docker/Dockerfile.web

# Not part of `check` (needs the vulnerability DB download). Triage the report in the change summary (SEC-092).
scan-images: ## scan the images with trivy (not part of check)
	mkdir -p .data
	$(CONTAINER) save -o .data/saveclock-api.tar saveclock-api:sha-$(GIT_SHA)
	$(CONTAINER) save -o .data/saveclock-worker.tar saveclock-worker:sha-$(GIT_SHA)
	for t in api worker; do \
	  $(CONTAINER) run --rm -v "$(CURDIR)/.data:/scan:ro,z" $(TRIVY) image --input /scan/saveclock-$$t.tar \
	    --severity HIGH,CRITICAL --exit-code 0 || exit 1; \
	done

# --- the stack (T-1.10) ------------------------------------------------------------------
up: ## sync flags, build images and start the stack
	scripts/sync_env_flags.sh
	$(MAKE) images
	$(MAKE) stack-up

# the compose half of `up` (no image build): the rollback demo runs it with IMAGE_TAG=<tag>
stack-up: ## start the stack on existing images (honours IMAGE_TAG)
	$(COMPOSE) up -d postgres redis
	CONTAINER=$(CONTAINER) scripts/wait_healthy.sh $(PROJECT) 120
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d

dev: up ## start the stack and wait until api and web are ready
	@for i in $$(seq 1 60); do \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$(API_PORT)/api/v1/health/ready); \
	  [ "$$code" = 200 ] && { echo "ready: $$code"; exit 0; }; sleep 2; done; \
	echo "api did not become ready"; exit 1
	@for i in $$(seq 1 60); do \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$(WEB_PORT)/healthz); \
	  [ "$$code" = 200 ] && { echo "web ready: $$code"; exit 0; }; sleep 2; done; \
	echo "web did not become ready"; exit 1

down: ## stop the stack, keep the data
	$(COMPOSE) down

down-volumes: ## delete the stack AND its volumes (needs CONFIRM=yes)
	@[ "$(CONFIRM)" = yes ] || { echo "this deletes the saveclock volumes (database, blobs): re-run with CONFIRM=yes"; exit 1; }
	$(COMPOSE) down -v

sandbox: ## check the running containers' hardening
	PROJECT=$(PROJECT) COMPOSE="$(COMPOSE)" CONTAINER=$(CONTAINER) scripts/verify_sandbox.sh

# --- the web shell (T-1.7, plan 002) ------------------------------------------------------
# Every target that runs node tooling depends on `guard` (the config-malware check) first.
web-install: guard ## install web dependencies from the lockfile
	pnpm install --frozen-lockfile

web-env: ## check web env names against .env.example
	scripts/check_web_env.sh

web-lint: guard ## lint, format-check and type-check the web code
	pnpm exec prettier --check apps packages
	pnpm --filter @saveclock/web lint
	pnpm --filter @saveclock/web typecheck
	pnpm --filter @saveclock/contracts exec tsc --noEmit

web-test: guard ## run the web unit tests
	pnpm --filter @saveclock/web test

web-build: guard ## build the web app
	pnpm --filter @saveclock/web build

bundle-scan: ## scan the web bundle for leaked secrets
	scripts/scan_bundle.sh

# Offline is a failure, not a silent skip; ALLOW_OFFLINE=1 accepts it on purpose. NPM_REGISTRY is
# overridable so the offline path can be exercised.
NPM_REGISTRY ?= https://registry.npmjs.org/
web-audit-prod: guard ## audit production web dependencies (needs network)
	@if ! curl -sfI --max-time 8 $(NPM_REGISTRY) >/dev/null 2>&1; then \
	  if [ "$(ALLOW_OFFLINE)" = 1 ]; then echo "SKIPPED (offline, ALLOW_OFFLINE=1): pnpm audit needs the network"; \
	  else echo "pnpm audit needs the network; set ALLOW_OFFLINE=1 to skip it on purpose"; exit 1; fi; \
	else pnpm audit --prod; fi

# stack-dependent (run after `make dev`); plan 003's bring-up runs them too. smoke-web covers the
# response headers as well (it absorbed the old web-headers check).
measure-rewrite: ## measure the upload and SSE path through the web rewrite
	PROJECT=$(PROJECT) python3 scripts/measure_rewrite.py --container $(CONTAINER)

smoke-web: ## smoke-test the running web shell
	python3 scripts/smoke_web.py

# Lighthouse is an exact-pinned devDependency of apps/web (in the lockfile), run with `pnpm exec`.
web-audit: guard ## run Lighthouse on the running web shell
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

seed: ## add one stub project to the running stack
	python3 scripts/smoke_stub.py --seed --web http://localhost:$(WEB_PORT) --api http://127.0.0.1:$(API_PORT)

smoke-stub: ## push a stub job through every hop
	COMPOSE="$(COMPOSE)" python3 scripts/smoke_stub.py --web http://localhost:$(WEB_PORT) \
	  --api http://127.0.0.1:$(API_PORT)

predeploy-scan: ## scan what is about to leave the machine
	scripts/predeploy_scan.sh .

backup: ## run one backup now
	$(STACK_ENV) bash infra/backup/backup.sh

# first run on a new backup folder: creates the (empty) restic repository, nothing else
backup-init: ## create the empty restic repository
	$(STACK_ENV) BACKUP_INIT=1 bash infra/backup/backup.sh

backup-test: ## run the backup script tests
	$(STACK_ENV) bash infra/backup/test_backup.sh

restore-proof: ## restore the latest backup into a scratch stack
	$(STACK_ENV) bash infra/backup/restore_proof.sh

# Writes to ~/.config/systemd/user and enables the timer: run it on the machine that should back up.
backup-install-timer: ## install the nightly backup timer
	@mkdir -p $(HOME)/.config/systemd/user
	@for u in saveclock-backup.service saveclock-backup.timer; do \
	  sed -e 's|@REPO@|$(CURDIR)|' -e 's|@PROJECT@|$(PROJECT)|' infra/backup/systemd/$$u > $(HOME)/.config/systemd/user/$$u; done
	systemctl --user daemon-reload
	systemctl --user enable --now saveclock-backup.timer
	systemctl --user list-timers saveclock-backup.timer --no-pager

backup-timer-uninstall: ## remove the nightly backup timer
	-systemctl --user disable --now saveclock-backup.timer
	rm -f $(HOME)/.config/systemd/user/saveclock-backup.service $(HOME)/.config/systemd/user/saveclock-backup.timer
	systemctl --user daemon-reload

rollback-demo: ## demonstrate a rollback between two image tags
	$(STACK_ENV) bash scripts/rollback_demo.sh

# make exports command-line variables, so TAG reaches the shell as $$TAG and is never pasted into the
# command text: a crafted TAG is judged by the regex before anything parses it.
rollback: ## run the stack on already built images: make rollback TAG=sha-<commit> (never restores or drops data; runs that tag's migrations)
	@[ -n "$$TAG" ] || { echo "usage: make rollback TAG=sha-<commit>   (built tags: $(CONTAINER) images saveclock-api)"; exit 2; }
	@printf '%s\n' "$$TAG" | grep -Eq '^sha-[0-9a-f]{7,40}$$' || { echo "TAG must look like sha-<commit>, got: $$TAG"; exit 2; }
	@for s in api worker web; do $(CONTAINER) image inspect "saveclock-$$s:$$TAG" >/dev/null 2>&1 || \
	  { echo "REFUSING: image saveclock-$$s:$$TAG does not exist locally. Check that commit out and run make images, or pick a tag from: $(CONTAINER) images"; exit 1; }; done
	IMAGE_TAG="$$TAG" $(MAKE) --no-print-directory stack-up

fresh-clone-timing: ## time a fresh clone to a running stack
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

check-fast: ## run the quality gate without image stages
	$(call run_stages,$(FAST_STAGES),CHECK-FAST OK)

check: ## run the full quality gate
	$(call run_stages,$(CHECK_STAGES),CHECK OK)
