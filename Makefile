.PHONY: install dev test integration lint migrate seed up down smoke

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --port 8000

test:
	uv run pytest -q

integration:
	RUN_INTEGRATION=1 uv run pytest -q

lint:
	uv run ruff check .
	uv run mypy app

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m app.executor.demo --job demo_pipeline

up:
	docker compose up -d --build

down:
	docker compose down

smoke:
	curl -s http://127.0.0.1:8000/health
