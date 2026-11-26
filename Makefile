SHELL := /bin/bash
.DEFAULT_GOAL := help
API := services/api
UV := uv --directory $(API)
COMPOSE_BIN := $(shell command -v docker >/dev/null 2>&1 && echo "docker compose" || echo "podman compose")
CONTAINER := $(shell command -v docker >/dev/null 2>&1 && echo docker || echo podman)
COMPOSE = $(COMPOSE_BIN) -p saveclock --env-file .env -f infra/compose/compose.yml
COMPOSE_TEST = $(COMPOSE_BIN) -p saveclock-test -f infra/compose/compose.test.yml
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
FFMPEG_SRC := $(HOME)/saveclock-spike/downloads/ffmpeg-9.0.x-static
HADOLINT := docker.io/hadolint/hadolint@sha256:9a3944b7fddcb947d1ffd90829ac1a6e5c30479223358f249d8b96c7d0019e27
TRIVY := ghcr.io/aquasecurity/trivy@sha256:6e7f515a46af13a01d534734c666261de65c6e6fe389fa2309e9e2d07470f3a8

# Stages, in order; the first failure stops the run and names the stage.
FAST_STAGES := guard secrets banned doctor env-docs-check fmt-check lint types arch pins \
  compose-lint test-deps-up test migrations contracts-check audit
CHECK_STAGES := $(FAST_STAGES) images image-guards hadolint

.PHONY: help guard secrets banned doctor fmt-check lint types arch pins compose-lint test \
  migrations audit env env-docs env-docs-check contracts contracts-check test-deps-up \
  test-deps-down ffmpeg-cache images image-guards hadolint scan-images up dev down \
  down-volumes sandbox check-fast check

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
	$(UV) run pytest -q -m "not golden and not live" --cov --cov-branch \
	  --cov-report=json:coverage.json --cov-fail-under=85
	python3 scripts/cov_floors.py

# alembic check (models == migration) and a downgrade -1 / upgrade head round trip
migrations:
	$(UV) run pytest -q -m integration tests/integration/test_migrations.py \
	  -k "alembic_check or one_step_roundtrip"

contracts:
	$(UV) run python ../../scripts/export_openapi.py

contracts-check: contracts
	git diff --exit-code packages/contracts/openapi.json

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

image-guards:
	CONTAINER=$(CONTAINER) scripts/check_image_contents.sh saveclock-api:sha-$(GIT_SHA) api
	CONTAINER=$(CONTAINER) scripts/check_image_contents.sh saveclock-worker:sha-$(GIT_SHA) worker
	@echo "IMAGE GUARDS OK"

hadolint:
	$(CONTAINER) run --rm -i $(HADOLINT) hadolint - < infra/docker/Dockerfile.api

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
	CONTAINER=$(CONTAINER) scripts/wait_healthy.sh saveclock 120
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d

dev: up
	@for i in $$(seq 1 60); do \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/v1/health/ready); \
	  [ "$$code" = 200 ] && { echo "ready: $$code"; exit 0; }; sleep 2; done; \
	echo "api did not become ready"; exit 1

down:
	$(COMPOSE) down

down-volumes:
	@[ "$(CONFIRM)" = yes ] || { echo "this deletes the saveclock volumes (database, blobs): re-run with CONFIRM=yes"; exit 1; }
	$(COMPOSE) down -v

sandbox:
	COMPOSE="$(COMPOSE)" CONTAINER=$(CONTAINER) scripts/verify_sandbox.sh

# --- gates -------------------------------------------------------------------------------
check-fast:
	@set -e; trap '$(MAKE) --no-print-directory test-deps-down >/dev/null 2>&1' EXIT; \
	for s in $(FAST_STAGES); do \
	  echo "==> stage $$s"; \
	  $(MAKE) --no-print-directory $$s || { echo "FAILED stage: $$s"; exit 2; }; \
	done; echo CHECK-FAST OK

check:
	@set -e; trap '$(MAKE) --no-print-directory test-deps-down >/dev/null 2>&1' EXIT; \
	for s in $(CHECK_STAGES); do \
	  echo "==> stage $$s"; \
	  $(MAKE) --no-print-directory $$s || { echo "FAILED stage: $$s"; exit 2; }; \
	done; echo CHECK OK
