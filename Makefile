.PHONY: help dev install precommit test lint format

help:
	@echo "Makefile targets: install, precommit, test, lint, format"

install:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt || true
	python -m pip install -r requirements-dev.txt || true

precommit:
	pre-commit install || true

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q

lint:
	ruff check . || true

format:
	black .
	isort .
.PHONY: setup test precommit

setup:
	./scripts/dev_setup.sh

precommit:
	pip install pre-commit
	pre-commit install

test:
	pytest -q
