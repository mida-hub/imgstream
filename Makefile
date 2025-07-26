.PHONY: help install install-dev test lint format type-check clean run pre-commit

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	uv sync --no-dev

install-dev: ## Install all dependencies including development tools
	uv sync

setup-env: ## Set up environment file from example
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file from .env.example"; \
		echo "Please edit .env file with your configuration"; \
	else \
		echo ".env file already exists"; \
	fi

test: ## Run tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=src/imgstream --cov-report=html --cov-report=term

lint: ## Run linting (ruff)
	uv run ruff check .

lint-fix: ## Run linting with auto-fix
	uv run ruff check . --fix

format: ## Format code with black
	uv run black .

format-check: ## Check code formatting
	uv run black . --check

type-check: ## Run type checking with mypy
	uv run mypy src/

security: ## Run security scans
	uv run bandit -r src/
	uv export --format requirements-txt --no-dev > requirements.txt
	uv run safety check --file requirements.txt
	rm -f requirements.txt

benchmark: ## Run performance benchmarks
	uv run pytest tests/performance/ --benchmark-only

quality: lint format-check type-check ## Run all code quality checks

quality-full: quality security test-cov ## Run comprehensive quality checks including security and coverage

ci-test: ## Run tests in CI mode (with coverage and XML output)
	ENVIRONMENT=production uv run pytest --cov=src --cov-report=xml --cov-report=term-missing

ci-quality: ## Run quality checks in CI mode
	./scripts/quality-check.sh -e production

clean: ## Clean up temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -f bandit-report.json safety-report.json coverage.xml requirements.txt

run: ## Run the Streamlit application
	uv run streamlit run src/imgstream/main.py

run-dev: ## Run the Streamlit application in development mode
	uv run streamlit run src/imgstream/main.py --server.runOnSave=true

pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install

pre-commit: ## Run pre-commit on all files
	uv run pre-commit run --all-files

dev-setup: install-dev setup-env pre-commit-install ## Complete development environment setup
	@echo "Development environment setup complete!"
	@echo "You can now run 'make run' to start the application"

docker-build: ## Build production Docker image
	docker build -t imgstream:latest .

docker-build-dev: ## Build development Docker image
	docker build -f Dockerfile.dev -t imgstream:dev .

docker-run: ## Run Docker container
	docker run -p 8080:8080 imgstream:latest

docker-run-dev: ## Run development Docker container with hot reload
	docker run -p 8501:8501 -v $(PWD)/src:/app/src imgstream:dev

docker-compose-up: ## Start services with docker compose
	docker compose up --build

docker-compose-dev: ## Start development services with docker compose
	docker compose --profile dev up --build

docker-compose-down: ## Stop docker compose services
	docker compose down

docker-clean: ## Clean up Docker images and containers
	docker system prune -f
	docker image prune -f
