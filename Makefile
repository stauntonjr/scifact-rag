.PHONY: check format-check lint typecheck unit integration package-smoke compose-config smoke

check:
	python3 tools/harness_check.py

format-check:
	uv run ruff format --check src tests

lint:
	uv run ruff check src tests

typecheck:
	uv run pyright

unit:
	uv run pytest -m 'not integration'

integration:
	uv run pytest -m integration

package-smoke:
	python3 tools/python_package_smoke.py

compose-config:
	docker compose config --quiet

smoke: check format-check lint typecheck unit package-smoke compose-config
