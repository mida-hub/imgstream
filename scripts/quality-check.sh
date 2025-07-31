#!/bin/bash

# ImgStream Quality Check Script
# This script runs comprehensive code quality checks including Black, Ruff, and MyPy

set -e

# Default values
ENVIRONMENT="development"
VERBOSE=false
FIX_MODE=false
PRODUCTION_MODE=false
EXIT_ON_ERROR=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_header() {
    echo ""
    print_status $BLUE "🔍 $1"
    echo "----------------------------------------"
}

print_success() {
    print_status $GREEN "✅ $1"
}

print_error() {
    print_status $RED "❌ $1"
}

print_warning() {
    print_status $YELLOW "⚠️  $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

ImgStream Quality Check Script

OPTIONS:
    -e, --environment ENV    Set environment (development|staging|production)
    -v, --verbose           Enable verbose output
    -f, --fix              Auto-fix issues where possible
    -p, --production       Run production-grade checks (includes tests)
    -c, --continue         Continue on errors (don't exit on first failure)
    -h, --help             Show this help message

EXAMPLES:
    $0                                    # Run basic quality checks
    $0 -e production                      # Run with production environment
    $0 -f                                # Run with auto-fix enabled
    $0 -p -v                             # Run production checks with verbose output
    $0 --fix --continue                   # Auto-fix and continue on errors

QUALITY CHECKS:
    1. Black    - Code formatting consistency
    2. Ruff     - Linting and code quality
    3. MyPy     - Static type checking
    4. Tests    - Unit tests (production mode only)

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -f|--fix)
            FIX_MODE=true
            shift
            ;;
        -p|--production)
            PRODUCTION_MODE=true
            shift
            ;;
        -c|--continue)
            EXIT_ON_ERROR=false
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to run command with error handling
run_check() {
    local check_name=$1
    local command=$2
    local fix_command=$3
    
    print_header "$check_name"
    
    if [[ $VERBOSE == true ]]; then
        print_status $BLUE "Command: $command"
    fi
    
    if eval "$command"; then
        print_success "$check_name: PASSED"
        return 0
    else
        print_error "$check_name: FAILED"
        
        if [[ $FIX_MODE == true && -n "$fix_command" ]]; then
            print_status $YELLOW "Attempting to auto-fix..."
            if eval "$fix_command"; then
                print_success "Auto-fix applied for $check_name"
                # Re-run the check after fix
                if eval "$command"; then
                    print_success "$check_name: PASSED (after fix)"
                    return 0
                else
                    print_error "$check_name: Still failing after auto-fix"
                fi
            else
                print_error "Auto-fix failed for $check_name"
            fi
        fi
        
        if [[ $EXIT_ON_ERROR == true ]]; then
            print_error "Exiting due to $check_name failure"
            exit 1
        fi
        return 1
    fi
}

# Main execution
main() {
    print_status $BLUE "🚀 Starting ImgStream Quality Checks"
    print_status $BLUE "Environment: $ENVIRONMENT"
    print_status $BLUE "Fix mode: $FIX_MODE"
    print_status $BLUE "Production mode: $PRODUCTION_MODE"
    echo ""
    
    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Please install uv first."
        exit 1
    fi
    
    # Set environment variable
    export ENVIRONMENT=$ENVIRONMENT
    
    local failed_checks=0
    
    # 1. Black - Code Formatting
    if [[ $FIX_MODE == true ]]; then
        run_check "Black (Auto-format)" \
                  "uv run black src/ tests/" \
                  ""
    else
        run_check "Black (Format Check)" \
                  "uv run black --check --diff src/ tests/" \
                  "uv run black src/ tests/"
    fi
    [[ $? -ne 0 ]] && ((failed_checks++))
    
    # 2. Ruff - Linting
    if [[ $FIX_MODE == true ]]; then
        run_check "Ruff (Auto-fix)" \
                  "uv run ruff check --fix src/ tests/" \
                  ""
    else
        run_check "Ruff (Linting)" \
                  "uv run ruff check src/ tests/" \
                  "uv run ruff check --fix src/ tests/"
    fi
    [[ $? -ne 0 ]] && ((failed_checks++))
    
    # 3. MyPy - Type Checking
    run_check "MyPy (Type Check)" \
              "uv run mypy src/" \
              ""
    [[ $? -ne 0 ]] && ((failed_checks++))
    
    # 4. Tests (Production mode only)
    if [[ $PRODUCTION_MODE == true ]]; then
        run_check "Tests (Production)" \
                  "ENVIRONMENT=production uv run pytest" \
                  ""
        [[ $? -ne 0 ]] && ((failed_checks++))
    fi
    
    # Summary
    echo ""
    print_header "Quality Check Summary"
    
    if [[ $failed_checks -eq 0 ]]; then
        print_success "🎉 All quality checks passed successfully!"
        
        if [[ $PRODUCTION_MODE == true ]]; then
            print_success "✨ Code is ready for production deployment!"
        else
            print_success "✨ Code meets quality standards!"
        fi
        
        echo ""
        print_status $BLUE "📊 Quality Check Details:"
        print_status $BLUE "- Black: Code formatting verification"
        print_status $BLUE "- Ruff: Linting and code quality checks"
        print_status $BLUE "- MyPy: Static type checking"
        if [[ $PRODUCTION_MODE == true ]]; then
            print_status $BLUE "- Tests: Unit and integration tests"
        fi
        
        exit 0
    else
        print_error "⚠️  $failed_checks quality check(s) failed"
        
        echo ""
        print_status $YELLOW "💡 To fix issues automatically, run:"
        print_status $YELLOW "   $0 --fix"
        
        print_status $YELLOW "💡 For manual fixes:"
        print_status $YELLOW "   - Black: uv run black src/ tests/"
        print_status $YELLOW "   - Ruff:  uv run ruff check --fix src/ tests/"
        print_status $YELLOW "   - MyPy:  Review type annotations"
        
        exit 1
    fi
}

# Run main function
main "$@"
