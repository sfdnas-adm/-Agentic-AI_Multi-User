.PHONY: lint format check test docker-build docker-up docker-down

# Code quality
lint:
	ruff check review_bot/

format:
	ruff format review_bot/

check: lint
	ruff format --check review_bot/

fix:
	ruff check --fix review_bot/
	ruff format review_bot/

# Docker commands
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f app

# Development
install:
	pip install -r requirements.txt

dev: install
	uvicorn review_bot.main:app --reload --host 0.0.0.0 --port 8000