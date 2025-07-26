# imgstream

Personal photo management web application with Streamlit

## Overview

imgstream is a web application for managing personal photo collections with features including:

- 📸 Photo upload and storage in Google Cloud Storage
- 🖼️ Thumbnail generation and display
- 🗃️ Metadata management with DuckDB
- 🔐 Cloud IAP authentication
- 💰 Cost-optimized storage with lifecycle policies

## Features

- **Secure Authentication**: Cloud IAP integration for secure access
- **Photo Upload**: Support for HEIC and JPEG formats from smartphones
- **Smart Storage**: Automatic lifecycle management (Standard → Coldline after 30 days)
- **Fast Browsing**: Thumbnail-based interface with chronological sorting
- **Metadata Management**: Efficient DuckDB-based metadata storage
- **Cost Optimized**: Designed to work within GCP free tier limits

## Technology Stack

- **Frontend**: Streamlit (Python)
- **Backend**: Python (Cloud Run)
- **Authentication**: Google Cloud IAP
- **Storage**: Google Cloud Storage
- **Database**: DuckDB
- **Image Processing**: Pillow, pillow-heif
- **Package Management**: uv
- **Infrastructure**: Terraform
- **Deployment**: Cloud Run

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Cloud SDK (for deployment)
- Docker (optional, for containerized development)

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd imgstream
```

2. Set up development environment:

```bash
make dev-setup
# This will install dependencies, create .env file, and set up pre-commit hooks
```

3. Edit environment variables (optional):

```bash
# Edit .env file with your specific configuration
vim .env
```

### Development Commands

```bash
# Run the application
make run

# Run tests
make test

# Run tests with coverage
make test-cov

# Code quality checks
make quality

# Format code
make format

# Run linting
make lint

# Type checking
make type-check

# Clean temporary files
make clean

# Docker commands
make docker-build          # Build production image
make docker-build-dev      # Build development image
make docker-run            # Run production container
make docker-run-dev        # Run development container
make docker-compose-up     # Start with docker compose
make docker-compose-dev    # Start development environment
make docker-compose-down   # Stop docker compose services
```

### Running the Application

```bash
# Development mode with auto-reload
make run-dev

# Or directly with uv
uv run streamlit run src/imgstream/main.py
```

## Project Structure

```
imgstream/
├── src/
│   └── imgstream/
│       ├── __init__.py
│       ├── main.py              # Streamlit application entry point
│       ├── services/            # Business logic services
│       │   ├── __init__.py
│       │   ├── auth.py          # Cloud IAP authentication
│       │   ├── storage.py       # GCS operations
│       │   ├── image_processor.py # Image processing
│       │   └── metadata.py      # DuckDB operations
│       └── models/              # Data models
│           ├── __init__.py
│           └── photo.py         # Photo metadata model
├── tests/                       # Test suite
├── terraform/                   # Infrastructure as code
├── .github/workflows/           # CI/CD pipelines
├── pyproject.toml              # Project configuration
├── Dockerfile                  # Container configuration
└── Makefile                    # Development commands
```

## Testing

The project uses pytest for testing with the following structure:

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test complete user workflows
- **Performance tests**: Benchmark critical operations

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test categories
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m e2e

# Run performance tests
uv run pytest tests/performance/ --benchmark-only

# Run quality checks
./scripts/quality-check.sh
```

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment:

### Workflows

1. **Test and Lint** (`.github/workflows/test.yml`)
   - Runs on every push and pull request
   - Code formatting check (black)
   - Import sorting (ruff)
   - Linting (ruff)
   - Type checking (mypy)
   - Unit and integration tests with coverage
   - Docker build test

2. **Security Scan** (`.github/workflows/security.yml`)
   - Daily security scans
   - Static analysis with Bandit
   - Dependency vulnerability scanning with Safety
   - CodeQL analysis
   - Dependency review for PRs

3. **Code Quality Analysis**
   - SonarCloud integration
   - Coverage reporting
   - Performance benchmarking

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run hooks on all files
uv run pre-commit run --all-files

# Update hooks
uv run pre-commit autoupdate
```

### Quality Gates

- **Code Coverage**: Minimum 80% coverage required
- **Security**: No high-severity security issues
- **Linting**: All ruff checks must pass
- **Type Checking**: All mypy checks must pass
- **Formatting**: Code must be formatted with black

## Deployment

### Infrastructure Setup

1. Configure Terraform:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

2. Deploy application:

```bash
# Build and push Docker image
make docker-build

# Deploy to Cloud Run (via CI/CD or manual)
gcloud run deploy imgstream --image gcr.io/PROJECT_ID/imgstream:latest
```

### Environment Variables

Required environment variables for deployment:

- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GCS_BUCKET`: Storage bucket name
- `GOOGLE_APPLICATION_CREDENTIALS`: Service account key path

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and quality checks: `make quality test`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Architecture

For detailed technical information, see the [design documentation](.kiro/specs/photo-management-app/design.md).
