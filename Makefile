.PHONY: help install install-dev test lint format type-check clean run pre-commit

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	uv sync --no-dev

install-dev: ## Install all dependencies including development tools
	uv sync

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

quality: lint format-check type-check ## Run all code quality checks

clean: ## Clean up temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/

run: ## Run the Streamlit application
	uv run streamlit run src/imgstream/main.py

run-dev: ## Run the Streamlit application in development mode
	uv run streamlit run src/imgstream/main.py --server.runOnSave=true

pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install

pre-commit: ## Run pre-commit on all files
	uv run pre-commit run --all-files

docker-build: ## Build Docker image
	docker build -t imgstream:latest .

docker-run: ## Run Docker container
	docker run -p 8080:8080 imgstream:latest
