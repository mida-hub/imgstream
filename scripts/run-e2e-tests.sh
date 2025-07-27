#!/bin/bash
# End-to-end test runner for imgstream

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_ENVIRONMENT="local"
APP_URL="http://localhost:8501"
PARALLEL_WORKERS=1
VERBOSE=false
COVERAGE=false
REPORT_FORMAT="terminal"
TEST_PATTERN="test_*.py"

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e ENVIRONMENT    Test environment (local|dev|staging) [default: local]"
    echo "  -u URL            Application URL [default: http://localhost:8501]"
    echo "  -w WORKERS        Number of parallel workers [default: 1]"
    echo "  -p PATTERN        Test file pattern [default: test_*.py]"
    echo "  -v                Verbose output"
    echo "  -c                Enable coverage reporting"
    echo "  -r FORMAT         Report format (terminal|html|xml) [default: terminal]"
    echo "  --auth-flow       Run only authentication flow tests"
    echo "  --upload-flow     Run only upload flow tests"
    echo "  --error-scenarios Run only error scenario tests"
    echo "  -h                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all E2E tests locally"
    echo "  $0 -e dev -u https://dev-app-url     # Run against dev environment"
    echo "  $0 --auth-flow -v                    # Run auth tests with verbose output"
    echo "  $0 -c -r html                        # Run with HTML coverage report"
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
            TEST_ENVIRONMENT="$2"
            shift 2
            ;;
        -u|--url)
            APP_URL="$2"
            shift 2
            ;;
        -w|--workers)
            PARALLEL_WORKERS="$2"
            shift 2
            ;;
        -p|--pattern)
            TEST_PATTERN="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -r|--report)
            REPORT_FORMAT="$2"
            shift 2
            ;;
        --auth-flow)
            TEST_PATTERN="test_authentication_flow.py"
            shift
            ;;
        --upload-flow)
            TEST_PATTERN="test_upload_flow.py"
            shift
            ;;
        --error-scenarios)
            TEST_PATTERN="test_error_scenarios.py"
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
if [[ ! "$TEST_ENVIRONMENT" =~ ^(local|dev|staging)$ ]]; then
    print_error "TEST_ENVIRONMENT must be 'local', 'dev', or 'staging'"
    exit 1
fi

# Display configuration
echo "=================================="
echo "    E2E Test Configuration"
echo "=================================="
echo "Environment:     $TEST_ENVIRONMENT"
echo "App URL:         $APP_URL"
echo "Workers:         $PARALLEL_WORKERS"
echo "Test Pattern:    $TEST_PATTERN"
echo "Verbose:         $VERBOSE"
echo "Coverage:        $COVERAGE"
echo "Report Format:   $REPORT_FORMAT"
echo "=================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed. Please install it first."
    exit 1
fi

# Install dependencies
print_status "Installing test dependencies..."
uv sync --dev

# Set environment variables for tests
export TEST_ENVIRONMENT="$TEST_ENVIRONMENT"
export TEST_APP_URL="$APP_URL"

# Prepare test command
TEST_CMD="uv run pytest tests/e2e/$TEST_PATTERN"

# Add verbose flag
if [[ "$VERBOSE" == "true" ]]; then
    TEST_CMD="$TEST_CMD -v"
fi

# Add parallel execution
if [[ "$PARALLEL_WORKERS" -gt 1 ]]; then
    TEST_CMD="$TEST_CMD -n $PARALLEL_WORKERS"
fi

# Add coverage
if [[ "$COVERAGE" == "true" ]]; then
    TEST_CMD="$TEST_CMD --cov=src/imgstream"
    
    case $REPORT_FORMAT in
        "html")
            TEST_CMD="$TEST_CMD --cov-report=html --cov-report=term"
            ;;
        "xml")
            TEST_CMD="$TEST_CMD --cov-report=xml --cov-report=term"
            ;;
        "terminal")
            TEST_CMD="$TEST_CMD --cov-report=term-missing"
            ;;
    esac
fi

# Add markers for E2E tests
TEST_CMD="$TEST_CMD -m e2e"

# Environment-specific setup
case $TEST_ENVIRONMENT in
    "local")
        print_status "Setting up local test environment..."
        
        # Check if local app is running
        if ! curl -f -s "$APP_URL/health" > /dev/null 2>&1; then
            print_warning "Local application not responding at $APP_URL"
            print_warning "Please start the application first:"
            print_warning "  make run"
            print_warning ""
            print_warning "Continuing with unit-style E2E tests..."
        else
            print_success "Local application is running at $APP_URL"
        fi
        ;;
        
    "dev")
        print_status "Setting up development environment tests..."
        
        # Verify dev environment is accessible
        if ! curl -f -s "$APP_URL/health" > /dev/null 2>&1; then
            print_error "Development environment not accessible at $APP_URL"
            exit 1
        fi
        
        print_success "Development environment is accessible"
        ;;
        
    "staging")
        print_status "Setting up staging environment tests..."
        
        # Verify staging environment is accessible
        if ! curl -f -s "$APP_URL/health" > /dev/null 2>&1; then
            print_error "Staging environment not accessible at $APP_URL"
            exit 1
        fi
        
        print_success "Staging environment is accessible"
        ;;
esac

# Create test results directory
mkdir -p test-results

# Run the tests
print_status "Running E2E tests..."
print_status "Command: $TEST_CMD"
echo ""

# Execute tests
if eval "$TEST_CMD"; then
    print_success "All E2E tests passed!"
    
    # Display coverage report location if generated
    if [[ "$COVERAGE" == "true" && "$REPORT_FORMAT" == "html" ]]; then
        print_status "Coverage report generated: htmlcov/index.html"
    fi
    
    exit 0
else
    print_error "Some E2E tests failed!"
    
    # Provide debugging information
    echo ""
    print_status "Debugging information:"
    echo "1. Check application logs"
    echo "2. Verify test environment setup"
    echo "3. Check network connectivity"
    echo "4. Review test output above"
    
    if [[ "$TEST_ENVIRONMENT" == "local" ]]; then
        echo ""
        print_status "For local testing:"
        echo "1. Ensure application is running: make run"
        echo "2. Check application health: curl $APP_URL/health"
        echo "3. Review application logs"
    fi
    
    exit 1
fi
