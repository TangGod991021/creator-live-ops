.PHONY: install dev test lint migrate seed up down

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --port 8000

test:
	uv run pytest -q

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
