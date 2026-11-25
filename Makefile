SHELL := /bin/bash
.DEFAULT_GOAL := help
API := services/api
UV := uv --directory $(API)
COMPOSE_BIN := $(shell command -v docker >/dev/null 2>&1 && echo "docker compose" || echo "podman compose")
CONTAINER := $(shell command -v docker >/dev/null 2>&1 && echo docker || echo podman)
COMPOSE = $(COMPOSE_BIN) -p saveclock --env-file .env -f infra/compose/compose.yml
COMPOSE_TEST = $(COMPOSE_BIN) -p saveclock-test -f infra/compose/compose.test.yml

.PHONY: help guard doctor fmt-check lint types test check-fast check env env-docs env-docs-check contracts contracts-check test-deps-up test-deps-down

env-docs:
	$(UV) run python ../../scripts/gen_env_docs.py

env-docs-check: env-docs
	@echo "==> stage env-docs-check"
	git diff --exit-code .env.example infra/ENV.md

env:
	scripts/gen_env.sh

test-deps-up:
	@echo "==> stage test-deps-up"
	$(COMPOSE_TEST) up -d
	CONTAINER=$(CONTAINER) scripts/wait_healthy.sh saveclock-test 90

test-deps-down:
	$(COMPOSE_TEST) down

contracts:
	$(UV) run python ../../scripts/export_openapi.py

contracts-check: contracts
	@echo "==> stage contracts-check"
	git diff --exit-code packages/contracts/openapi.json

help:
	@echo "targets: check-fast check dev down sandbox (see Makefile)"

guard:
	@echo "==> stage guard"
	scripts/check-config-malware.sh --deep .

doctor:
	scripts/check_toolchain.sh

fmt-check:
	@echo "==> stage fmt-check"
	$(UV) run ruff format --check .

lint:
	@echo "==> stage lint"
	$(UV) run ruff check .

types:
	@echo "==> stage types"
	$(UV) run mypy

test:
	@echo "==> stage test"
	$(UV) run pytest -q

check-fast: guard doctor fmt-check lint types test
	@echo CHECK-FAST OK

check: check-fast
	@echo CHECK OK
