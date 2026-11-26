SHELL := /bin/bash
.DEFAULT_GOAL := help
API := services/api
UV := uv --directory $(API)
COMPOSE_BIN := $(shell command -v docker >/dev/null 2>&1 && echo "docker compose" || echo "podman compose")
CONTAINER := $(shell command -v docker >/dev/null 2>&1 && echo docker || echo podman)
COMPOSE = $(COMPOSE_BIN) -p saveclock --env-file .env -f infra/compose/compose.yml
COMPOSE_TEST = $(COMPOSE_BIN) -p saveclock-test -f infra/compose/compose.test.yml

# check-fast stages, in order (stops at the first failure)
FAST_STAGES := guard secrets banned doctor env-docs-check fmt-check lint types arch \
  test-deps-up test migrations contracts-check audit

.PHONY: help guard secrets banned doctor fmt-check lint types arch test migrations audit \
  env env-docs env-docs-check contracts contracts-check test-deps-up test-deps-down \
  check-fast check

help:
	@echo "targets: check-fast check test-deps-up test-deps-down env env-docs contracts"

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

check-fast:
	@set -e; trap '$(MAKE) --no-print-directory test-deps-down >/dev/null 2>&1' EXIT; \
	for s in $(FAST_STAGES); do \
	  echo "==> stage $$s"; \
	  $(MAKE) --no-print-directory $$s || { echo "FAILED stage: $$s"; exit 2; }; \
	done; echo CHECK-FAST OK

check: check-fast
	@echo CHECK OK
