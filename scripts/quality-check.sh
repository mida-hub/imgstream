#!/bin/bash
# Code quality check script for imgstream

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="production"
SKIP_TESTS=false
SKIP_SECURITY=false
VERBOSE=false

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e ENVIRONMENT    Environment (production|development) [default: production]"
    echo "  --skip-tests      Skip running tests"
    echo "  --skip-security   Skip security scans"
    echo "  -v, --verbose     Verbose output"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Run all checks in production mode"
    echo "  $0 -e development            # Run checks in development mode"
    echo "  $0 --skip-tests --skip-security  # Run only linting and formatting checks"
    exit 1
}

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-security)
            SKIP_SECURITY=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(production|development)$ ]]; then
    print_error "ENVIRONMENT must be 'production' or 'development'"
    exit 1
fi

echo "=================================="
echo "    Code Quality Check"
echo "=================================="
echo "Environment:     $ENVIRONMENT"
echo "Skip Tests:      $SKIP_TESTS"
echo "Skip Security:   $SKIP_SECURITY"
echo "Verbose:         $VERBOSE"
echo "=================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed. Please install it first."
    exit 1
fi

# Install dependencies
print_status "Installing dependencies..."
uv sync --dev

# Set verbose flag for commands
VERBOSE_FLAG=""
if [[ "$VERBOSE" == "true" ]]; then
    VERBOSE_FLAG="-v"
fi

# 1. Code formatting check
print_status "Checking code formatting with black..."
if uv run black --check --diff . $VERBOSE_FLAG; then
    print_success "Code formatting is correct"
else
    print_error "Code formatting issues found. Run 'uv run black .' to fix them."
    exit 1
fi

# 2. Import sorting check
print_status "Checking import sorting with ruff..."
if uv run ruff check --select I . $VERBOSE_FLAG; then
    print_success "Import sorting is correct"
else
    print_error "Import sorting issues found. Run 'uv run ruff check --select I --fix .' to fix them."
    exit 1
fi

# 3. Linting
print_status "Running linting with ruff..."
if uv run ruff check . $VERBOSE_FLAG; then
    print_success "Linting passed"
else
    print_error "Linting issues found. Run 'uv run ruff check --fix .' to fix auto-fixable issues."
    exit 1
fi

# 4. Type checking
print_status "Running type checking with mypy..."
if uv run mypy src/ $VERBOSE_FLAG; then
    print_success "Type checking passed"
else
    print_error "Type checking issues found"
    exit 1
fi

# 5. Tests
if [[ "$SKIP_TESTS" == "false" ]]; then
    print_status "Running tests with pytest..."
    if [[ "$ENVIRONMENT" == "production" ]]; then
        # Production: Run with coverage
        if uv run pytest --cov=src --cov-report=term-missing --cov-report=xml $VERBOSE_FLAG; then
            print_success "All tests passed"
        else
            print_error "Some tests failed"
            exit 1
        fi
    else
        # Development: Run without coverage for speed
        if uv run pytest $VERBOSE_FLAG; then
            print_success "All tests passed"
        else
            print_error "Some tests failed"
            exit 1
        fi
    fi
else
    print_warning "Skipping tests"
fi

# 6. Security scans
if [[ "$SKIP_SECURITY" == "false" ]]; then
    print_status "Running security scan with bandit..."
    if uv run bandit -r src/ $VERBOSE_FLAG; then
        print_success "Security scan passed"
    else
        print_warning "Security issues found. Please review the output above."
    fi
    
    print_status "Running dependency vulnerability scan with safety..."
    # Export requirements for safety check
    uv export --format requirements-txt --no-dev > requirements.txt
    if uv run safety check --file requirements.txt; then
        print_success "Dependency vulnerability scan passed"
    else
        print_warning "Vulnerable dependencies found. Please review the output above."
    fi
    # Clean up temporary file
    rm -f requirements.txt
else
    print_warning "Skipping security scans"
fi

# 7. Check for TODO/FIXME comments in production
if [[ "$ENVIRONMENT" == "production" ]]; then
    print_status "Checking for TODO/FIXME comments..."
    TODO_COUNT=$(grep -r "TODO\|FIXME" src/ --include="*.py" | wc -l || echo "0")
    if [[ "$TODO_COUNT" -gt 0 ]]; then
        print_warning "Found $TODO_COUNT TODO/FIXME comments in source code"
        if [[ "$VERBOSE" == "true" ]]; then
            grep -r "TODO\|FIXME" src/ --include="*.py" || true
        fi
    else
        print_success "No TODO/FIXME comments found"
    fi
fi

# 8. Check test coverage (production only)
if [[ "$ENVIRONMENT" == "production" && "$SKIP_TESTS" == "false" ]]; then
    print_status "Checking test coverage..."
    COVERAGE=$(uv run coverage report --format=total 2>/dev/null || echo "0")
    if [[ "$COVERAGE" -ge 80 ]]; then
        print_success "Test coverage is ${COVERAGE}% (>= 80%)"
    else
        print_warning "Test coverage is ${COVERAGE}% (< 80%)"
    fi
fi

echo ""
echo "=================================="
echo "    Quality Check Summary"
echo "=================================="
echo "Environment:     $ENVIRONMENT"
echo "All checks:      PASSED"
echo "=================================="
echo ""

print_success "All quality checks completed successfully!"

# Additional recommendations
echo ""
echo "Recommendations:"
echo "1. Run 'uv run pre-commit install' to set up pre-commit hooks"
echo "2. Run 'uv run pre-commit run --all-files' to check all files"
echo "3. Consider running 'uv run pytest --benchmark-only' for performance tests"
