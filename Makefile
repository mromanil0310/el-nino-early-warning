.PHONY: help install install-dev test preview lint-yaml build-dashboard

# Override with `make PYTHON=python` if `python3` isn't your interpreter name.
PYTHON ?= python3

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## Install the full pipeline runtime (Airflow, dbt, Supabase, pdfplumber, Anthropic)
	$(PYTHON) -m pip install -r pipeline/requirements.txt

install-dev:  ## Install just what the unit tests need (pytest + pyyaml)
	$(PYTHON) -m pip install -r pipeline/requirements-dev.txt

test:  ## Run the Python unit tests
	$(PYTHON) -m pytest pipeline/tests -v

preview:  ## Offline risk-score preview for a given date (no DB) — make preview DATE=2026-09-01
	$(PYTHON) pipeline/scripts/preview_run.py $(DATE)

lint-yaml:  ## Validate the dbt schema/sources YAML
	$(PYTHON) -c "import yaml; yaml.safe_load(open('pipeline/models/schema.yml')); yaml.safe_load(open('pipeline/models/sources.yml')); print('dbt yml ok')"

build-dashboard:  ## Install + build the Next.js dashboard
	cd dashboard && npm ci && npm run build
