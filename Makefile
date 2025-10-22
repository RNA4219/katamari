.PHONY: dev run fmt lint type test docker help check ci

dev:
	pip install -r requirements.txt

run:
	chainlit run src/app.py --host 0.0.0.0 --port 8787

fmt:
	ruff format .

lint:
	ruff check .

type:
	mypy --strict

test:
	pytest -q

check: lint type test

ci:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt ruff mypy pytest
	ruff check .
	mypy --strict
	pytest -q
	pnpm --dir upstream/chainlit install --frozen-lockfile
	pnpm --dir upstream/chainlit lint
	pnpm --dir upstream/chainlit test

help:
	@printf '%s\n' 'Available targets:'
	@printf '%s\n' '  dev    Install Python dependencies'
	@printf '%s\n' '  run    Start Chainlit development server'
	@printf '%s\n' '  fmt    Format code with ruff format'
	@printf '%s\n' '  lint   Run ruff check .'
	@printf '%s\n' '  type   Run mypy --strict'
	@printf '%s\n' '  test   Run pytest -q'
	@printf '%s\n' '  check  Run lint, type, and test checks'

