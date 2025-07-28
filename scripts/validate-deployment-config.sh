#!/bin/bash

# Deployment configuration validation script for ImgStream
# Validates environment configurations, secrets, and deployment readiness

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}\")\" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT=${ENVIRONMENT:-staging}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validation results
VALIDATION_ERRORS=0
VALIDATION_WARNINGS=0

# Add error
add_error() {
    log_error "$1"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
}

# Add warning
add_warning() {
    log_warning "$1"
    VALIDATION_WARNINGS=$((VALIDATION_WARNINGS + 1))
}

# Validate environment configuration files
validate_config_files() {
    log_info "Validating configuration files..."
    
    local config_file="$PROJECT_ROOT/config/environments/${ENVIRONMENT}.yaml"
    
    if [[ ! -f "$config_file" ]]; then
        add_error "Configuration file not found: $config_file"
        return 1
    fi
    
    log_success "Configuration file exists: $config_file"
    
    # Validate YAML syntax
    if ! python3 -c "import yaml; yaml.safe_load(open('$config_file'))" 2>/dev/null; then
        add_error "Invalid YAML syntax in $config_file"
        return 1
    fi
    
    log_success "Configuration file has valid YAML syntax"
    
    # Validate required configuration sections
    local required_sections=("environment" "app" "auth" "storage" "database" "performance" "security" "monitoring")
    
    for section in "${required_sections[@]}"; do
        if ! python3 -c "import yaml; config=yaml.safe_load(open('$config_file')); exit(0 if '$section' in config else 1)" 2>/dev/null; then
            add_error "Missing required configuration section: $section"
        else
            log_success "Configuration section exists: $section"
        fi
    done
}

# Validate environment variables
validate_environment_variables() {
    log_info "Validating environment variables..."
    
    # Required environment variables
    local required_vars=("GOOGLE_CLOUD_PROJECT")
    
    # Environment-specific variables
    case $ENVIRONMENT in
        production)
            required_vars+=("GCS_BUCKET_PRODUCTION" "IAP_AUDIENCE")
            ;;
        staging)
            required_vars+=("GCS_BUCKET_STAGING")
            ;;
    esac
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            add_error "Required environment variable not set: $var"
        else
            log_success "Environment variable set: $var"
        fi
    done
}

# Validate Google Cloud configuration
validate_gcp_config() {
    log_info "Validating Google Cloud configuration..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        add_error "gcloud CLI not installed"
        return 1
    fi
    
    log_success "gcloud CLI is installed"
    
    # Check authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null; then
        add_error "No active gcloud authentication found"
        return 1
    fi
    
    local active_account
    active_account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1)
    log_success "Active gcloud account: $active_account"
    
    # Check project configuration
    local current_project
    current_project=$(gcloud config get-value project 2>/dev/null || echo "")\n    \n    if [[ -z "$current_project" ]]; then\n        add_error "No default project set in gcloud config"\n    elif [[ "$current_project" != "${GOOGLE_CLOUD_PROJECT:-}" ]]; then\n        add_warning "gcloud project ($current_project) differs from GOOGLE_CLOUD_PROJECT (${GOOGLE_CLOUD_PROJECT:-})"
    else
        log_success "gcloud project matches: $current_project"
    fi
    
    # Check required APIs
    local required_apis=("run.googleapis.com" "cloudbuild.googleapis.com" "containerregistry.googleapis.com" "storage.googleapis.com")
    
    for api in "${required_apis[@]}"; do
        if gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
            log_success "API enabled: $api"
        else
            add_error "Required API not enabled: $api"
        fi
    done
}

# Validate Docker configuration
validate_docker_config() {
    log_info "Validating Docker configuration..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        add_error "Docker not installed"
        return 1
    fi
    
    log_success "Docker is installed"
    
    # Check if Docker daemon is running
    if ! docker info > /dev/null 2>&1; then
        add_error "Docker daemon is not running"
        return 1
    fi
    
    log_success "Docker daemon is running"
    
    # Check Docker authentication for GCR
    if ! gcloud auth configure-docker --quiet 2>/dev/null; then
        add_warning "Failed to configure Docker for GCR authentication"
    else
        log_success "Docker configured for GCR authentication"
    fi
}

# Validate deployment files
validate_deployment_files() {
    log_info "Validating deployment files..."
    
    local required_files=(
        "Dockerfile"
        "app.yaml"
        "cloudbuild.yaml"
        ".github/workflows/deploy.yml"
        "scripts/deploy-cloud-run.sh"
    )
    
    for file in "${required_files[@]}"; do
        local file_path="$PROJECT_ROOT/$file"
        if [[ ! -f "$file_path" ]]; then
            add_error "Required deployment file not found: $file"
        else
            log_success "Deployment file exists: $file"
        fi
    done
    
    # Validate Dockerfile
    if [[ -f "$PROJECT_ROOT/Dockerfile" ]]; then
        if grep -q "FROM python:" "$PROJECT_ROOT/Dockerfile"; then
            log_success "Dockerfile has valid Python base image"
        else
            add_warning "Dockerfile may not have a valid Python base image"
        fi
    fi
}

# Validate service accounts and IAM
validate_iam_config() {
    log_info "Validating IAM configuration..."
    
    local service_account="imgstream-cloud-run-${ENVIRONMENT}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
    
    # Check if service account exists
    if gcloud iam service-accounts describe "$service_account" > /dev/null 2>&1; then
        log_success "Service account exists: $service_account"
    else
        add_error "Service account not found: $service_account"
    fi
    
    # Check Cloud Build service account
    local cloudbuild_sa="cloudbuild-${ENVIRONMENT}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
    if gcloud iam service-accounts describe "$cloudbuild_sa" > /dev/null 2>&1; then
        log_success "Cloud Build service account exists: $cloudbuild_sa"
    else
        add_warning "Cloud Build service account not found: $cloudbuild_sa"
    fi
}

# Validate storage configuration
validate_storage_config() {
    log_info "Validating storage configuration..."
    
    case $ENVIRONMENT in
        production)
            local bucket="${GCS_BUCKET_PRODUCTION:-}"
            ;;
        staging)
            local bucket="${GCS_BUCKET_STAGING:-}"
            ;;
        *)
            log_info "Skipping storage validation for development environment"
            return 0
            ;;
    esac
    
    if [[ -n "$bucket" ]]; then
        if gsutil ls "gs://$bucket" > /dev/null 2>&1; then
            log_success "GCS bucket accessible: $bucket"
        else
            add_error "GCS bucket not accessible: $bucket"
        fi
    fi
}

# Validate network configuration
validate_network_config() {
    log_info "Validating network configuration..."
    
    # Check if required network resources exist for production
    if [[ "$ENVIRONMENT" == "production" ]]; then
        # In a real setup, you would check VPC, subnets, load balancers, etc.
        log_info "Network validation for production environment (placeholder)"
    fi
    
    log_success "Network configuration validation completed"
}

# Validate secrets and credentials
validate_secrets() {
    log_info "Validating secrets and credentials..."
    
    # Check for sensitive files that shouldn't be in version control
    local sensitive_files=(".env" "service-account-key.json" "credentials.json")
    
    for file in "${sensitive_files[@]}"; do
        if [[ -f "$PROJECT_ROOT/$file" ]]; then
            add_warning "Sensitive file found in project root: $file (should not be in version control)"
        fi
    done
    
    # Check .gitignore for sensitive patterns
    if [[ -f "$PROJECT_ROOT/.gitignore" ]]; then
        local gitignore_patterns=("*.env" "service-account-key.json" "credentials.json")
        
        for pattern in "${gitignore_patterns[@]}"; do
            if grep -q "$pattern" "$PROJECT_ROOT/.gitignore"; then
                log_success ".gitignore includes pattern: $pattern"
            else
                add_warning ".gitignore missing pattern: $pattern"
            fi
        done
    else
        add_warning ".gitignore file not found"
    fi
}

# Run all validations
run_all_validations() {
    log_info "Starting deployment configuration validation for environment: $ENVIRONMENT"
    echo ""
    
    validate_config_files
    echo ""
    
    validate_environment_variables
    echo ""
    
    validate_gcp_config
    echo ""
    
    validate_docker_config
    echo ""
    
    validate_deployment_files
    echo ""
    
    validate_iam_config
    echo ""
    
    validate_storage_config
    echo ""
    
    validate_network_config
    echo ""
    
    validate_secrets
    echo ""
}

# Generate validation report
generate_report() {
    echo "=================================="
    echo "DEPLOYMENT VALIDATION REPORT"
    echo "=================================="
    echo "Environment: $ENVIRONMENT"
    echo "Timestamp: $(date)"
    echo ""
    
    if [[ $VALIDATION_ERRORS -eq 0 && $VALIDATION_WARNINGS -eq 0 ]]; then
        log_success "✅ All validations passed! Deployment is ready."
        echo ""
        echo "Next steps:"
        echo "1. Run deployment: ./scripts/deploy-cloud-run.sh"
        echo "2. Monitor deployment: ./scripts/deployment-monitor.sh monitor"
        return 0
    else
        echo "Summary:"
        echo "  Errors: $VALIDATION_ERRORS"
        echo "  Warnings: $VALIDATION_WARNINGS"
        echo ""
        
        if [[ $VALIDATION_ERRORS -gt 0 ]]; then
            log_error "❌ Validation failed with $VALIDATION_ERRORS error(s). Please fix errors before deployment."
            echo ""
            echo "Common fixes:"
            echo "1. Set required environment variables"
            echo "2. Enable required Google Cloud APIs"
            echo "3. Create missing service accounts"
            echo "4. Configure authentication"
            return 1
        else
            log_warning "⚠️  Validation completed with $VALIDATION_WARNINGS warning(s). Review warnings before deployment."
            return 0
        fi
    fi
}

# Main execution
main() {
    run_all_validations
    generate_report
}

# Handle command line arguments
case "${1:-}" in
    --environment=*)
        ENVIRONMENT="${1#*=}"
        main
        ;;
    *)
        if [[ -n "${1:-}" ]]; then
            ENVIRONMENT="$1"
        fi
        main
        ;;
esac
