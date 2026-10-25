UV ?= uv
ENV ?= dev
C ?=
WEB := components/web_ui
PY_SRC := $(filter-out $(WEB)/src,$(wildcard components/*/src))
MYPY_PATHS := components/shared/src components/country_packs/src components/router/src
.DEFAULT_GOAL := help

.PHONY: help setup lint test test-int build package-budget plan apply destroy ingest run e2e evals load-test openapi

help:
	@echo "make setup                 install Python and web_ui deps, pre-commit hooks"
	@echo "make lint                  ruff, mypy, import-linter, web_ui lint, terraform fmt, tflint"
	@echo "make test [C=name]         unit tests for everything, or one component"
	@echo "make test-int              integration tests (needs a deployed env)"
	@echo "make build C=name          build one deployable component's image or package"
	@echo "make plan ENV=dev          terraform plan"
	@echo "make apply ENV=dev         terraform apply (human approval required)"
	@echo "make destroy ENV=dev       terraform destroy (human approval required)"
	@echo "make ingest                load policy docs into AI Search"
	@echo "make run [FAKE=1]           run agent_app, claims_api and web_ui locally (FAKE=1: offline fake model)"
	@echo "make e2e                   Playwright happy path against make run"
	@echo "make evals                 full golden set"
	@echo "make package-budget        zip the budget controller for the function app"
	@echo "make load-test             tools/load_test.py"
	@echo "make openapi               export agent_app/openapi.json for the web UI client"

setup:
	$(UV) sync --all-packages
	pnpm -C $(WEB) install
	@$(UV) run pre-commit install || echo "pre-commit not installed (not a git repo yet?)"

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy $(MYPY_PATHS) $(filter-out $(MYPY_PATHS),$(PY_SRC))
	$(UV) run lint-imports
	pnpm -C $(WEB) lint
	pnpm -C $(WEB) typecheck
	@if [ -d infra ]; then terraform fmt -check -recursive infra; fi
	@if command -v tflint >/dev/null 2>&1; then tflint --recursive; else echo "tflint not installed, skipped"; fi

test:
ifeq ($(C),)
	$(UV) run pytest
	$(UV) run pytest components/router/tests -q --cov=router --cov-branch --cov-fail-under=100
	pnpm -C $(WEB) run --if-present test
else ifeq ($(C),web_ui)
	pnpm -C $(WEB) run --if-present test
else
	@test -d components/$(C)/tests || { echo "no such component: $(C)"; exit 1; }
	$(UV) run pytest components/$(C)/tests
	@if [ "$(C)" = "router" ]; then $(UV) run pytest components/router/tests -q --cov=router --cov-branch --cov-fail-under=100; fi
endif

test-int:
	@if [ -n "$$(find tests/integration -name 'test_*.py' 2>/dev/null)" ]; then $(UV) run pytest tests/integration -m integration; else echo "not implemented yet (F-018): no integration tests"; fi

build:
	@test -n "$(C)" || { echo "usage: make build C=<agent_app|claims_api|web_ui>"; exit 1; }
	@test -f components/$(C)/Dockerfile || { echo "not implemented yet: no Dockerfile for $(C)"; exit 0; }
	docker build -f components/$(C)/Dockerfile -t kalayaan-$(C):dev .

plan:
	@if [ -f infra/envs/$(ENV)/main.tf ]; then terraform -chdir=infra/envs/$(ENV) init -input=false && terraform -chdir=infra/envs/$(ENV) plan -input=false; else echo "not implemented yet (F-009): infra/envs/$(ENV)"; fi

apply:
	@if [ -f infra/envs/$(ENV)/main.tf ]; then terraform -chdir=infra/envs/$(ENV) apply; else echo "not implemented yet (F-009): infra/envs/$(ENV)"; fi

destroy:
	@if [ -f infra/envs/$(ENV)/main.tf ]; then terraform -chdir=infra/envs/$(ENV) destroy; else echo "not implemented yet (F-009): infra/envs/$(ENV)"; fi

ingest:
	$(UV) run --package rag ingest

run:
	$(UV) run python tools/run_local.py --uv $(UV) $(if $(FAKE),--fake,)

e2e:
	UV=$(UV) pnpm -C $(WEB) e2e

evals:
	@echo "not implemented yet (F-036)"

package-budget:
	$(UV) run python tools/package_budget_function.py

load-test:
	$(UV) run python tools/load_test.py $(ARGS)

openapi:
	$(UV) run --package agent_app python -m agent_app.export_openapi
