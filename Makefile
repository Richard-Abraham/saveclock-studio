SHELL := /bin/bash
.DEFAULT_GOAL := help
# compose project name; override to keep a second checkout's volumes apart (PROJECT=saveclock-x make dev)
PROJECT ?= saveclock
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
  compose-lint test-deps-up test migrations web-install contracts-check audit \
  web-env web-lint web-test web-build bundle-scan web-audit-prod
CHECK_STAGES := $(FAST_STAGES) images image-guards hadolint

.PHONY: help guard secrets banned doctor fmt-check lint types arch pins compose-lint test \
  migrations audit env env-docs env-docs-check contracts contracts-check test-deps-up \
  test-deps-down ffmpeg-cache images image-guards hadolint scan-images up dev down \
  down-volumes sandbox check-fast check web-install web-env web-lint web-test web-build \
  bundle-scan web-audit-prod web-headers measure-rewrite smoke-web web-audit

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
	$(UV) run pytest -q -m "not golden and not live and not migration_roundtrip" --cov --cov-branch \
	  --cov-report=json:coverage.json --cov-fail-under=85
	python3 scripts/cov_floors.py

# alembic check (models == migration) and a downgrade -1 / upgrade head round trip
migrations:
	$(UV) run pytest -q -m migration_roundtrip

# openapi.json from the Python models, then the TS types from openapi.json (T-1.4a)
contracts:
	$(UV) run python ../../scripts/export_openapi.py
	pnpm --filter @saveclock/contracts generate

# Regenerates into a temp dir and compares with the checked-in files, so a hand edit of either
# file, a stale regeneration and an un-regenerated Python change all fail (and nothing is overwritten).
contracts-check: guard
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	$(UV) run python -c "from saveclock.export import openapi_json; print(openapi_json(), end='')" >"$$tmp/openapi.json"; \
	pnpm --filter @saveclock/contracts exec openapi-typescript "$$tmp/openapi.json" -o "$$tmp/schema.d.ts" >/dev/null; \
	diff -u packages/contracts/openapi.json "$$tmp/openapi.json" || { echo "CONTRACT DRIFT: openapi.json differs from the Python models (run make contracts)"; exit 1; }; \
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

images: ffmpeg-cache
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
	$(COMPOSE) up -d postgres redis
	CONTAINER=$(CONTAINER) scripts/wait_healthy.sh $(PROJECT) 120
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d

dev: up
	@for i in $$(seq 1 60); do \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/v1/health/ready); \
	  [ "$$code" = 200 ] && { echo "ready: $$code"; exit 0; }; sleep 2; done; \
	echo "api did not become ready"; exit 1
	@for i in $$(seq 1 60); do \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/healthz); \
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

# stack-dependent (run after `make dev`); plan 003's bring-up runs them too
web-headers:
	python3 scripts/check_web_headers.py

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
