#!/bin/bash

# Terraform validation script for imgstream
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✓${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}✗${NC} $message"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        "INFO")
            echo -e "${YELLOW}ℹ${NC} $message"
            ;;
    esac
}

# Set working directory to terraform root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$TERRAFORM_ROOT"

print_status "INFO" "Starting Terraform validation for new modular structure..."
print_status "INFO" "Working Directory: $TERRAFORM_ROOT"

# Check if terraform is installed
if command -v terraform &> /dev/null; then
    TERRAFORM_VERSION=$(terraform version -json | jq -r '.terraform_version')
    print_status "SUCCESS" "Terraform installed (version: $TERRAFORM_VERSION)"
else
    print_status "ERROR" "Terraform is not installed"
    exit 1
fi

# Check if gcloud is installed
if command -v gcloud &> /dev/null; then
    GCLOUD_VERSION=$(gcloud version --format="value(Google Cloud SDK)")
    print_status "SUCCESS" "gcloud CLI installed (version: $GCLOUD_VERSION)"
else
    print_status "ERROR" "gcloud CLI is not installed"
    exit 1
fi

# Check if jq is installed (for JSON parsing)
if ! command -v jq &> /dev/null; then
    print_status "WARNING" "jq is not installed (recommended for JSON parsing)"
fi

# Validate each environment
ENVIRONMENTS=("common" "dev" "prod")

for env in "${ENVIRONMENTS[@]}"; do
    print_status "INFO" "Validating $env environment..."
    
    if [[ ! -d "$env" ]]; then
        print_status "ERROR" "Environment directory not found: $env"
        continue
    fi
    
    cd "$env"
    
    # Initialize Terraform
    print_status "INFO" "Initializing Terraform for $env..."
    if terraform init -backend=false > /dev/null 2>&1; then
        print_status "SUCCESS" "Terraform initialized successfully for $env"
    else
        print_status "ERROR" "Terraform initialization failed for $env"
        cd ..
        continue
    fi
    
    # Validate Terraform configuration
    print_status "INFO" "Validating Terraform configuration for $env..."
    if terraform validate > /dev/null 2>&1; then
        print_status "SUCCESS" "Terraform configuration is valid for $env"
    else
        print_status "ERROR" "Terraform configuration validation failed for $env"
        terraform validate
        cd ..
        continue
    fi
    
    # Format check
    print_status "INFO" "Checking Terraform formatting for $env..."
    if terraform fmt -check -recursive > /dev/null 2>&1; then
        print_status "SUCCESS" "Terraform files are properly formatted for $env"
    else
        print_status "WARNING" "Some Terraform files need formatting in $env"
        print_status "INFO" "Run 'terraform fmt -recursive' in $env directory to fix formatting"
    fi
    
    cd ..
done

# Check for required files in each environment
print_status "INFO" "Checking for required files in each environment..."

# Common environment files
COMMON_FILES=("main.tf" "variables.tf" "outputs.tf" "github-oidc.tf" "terraform.tfvars")
print_status "INFO" "Checking common environment files..."
for file in "${COMMON_FILES[@]}"; do
    if [[ -f "common/$file" ]]; then
        print_status "SUCCESS" "Found: common/$file"
    else
        print_status "ERROR" "Missing: common/$file"
    fi
done

# Dev/Prod environment files
ENV_FILES=("main.tf" "variables.tf" "outputs.tf")
for env in "dev" "prod"; do
    print_status "INFO" "Checking $env environment files..."
    for file in "${ENV_FILES[@]}"; do
        if [[ -f "$env/$file" ]]; then
            print_status "SUCCESS" "Found: $env/$file"
        else
            print_status "ERROR" "Missing: $env/$file"
        fi
    done
    
    # Check tfvars file
    if [[ -f "$env/${env}.tfvars" ]]; then
        print_status "SUCCESS" "Found: $env/${env}.tfvars"
    else
        print_status "ERROR" "Missing: $env/${env}.tfvars"
    fi
done

# Check modules
print_status "INFO" "Checking modules..."
MODULE_FILES=("main.tf" "variables.tf" "outputs.tf" "storage.tf" "cloud_run.tf" "artifact_registry.tf" "iap.tf" "security.tf" "monitoring.tf")
for file in "${MODULE_FILES[@]}"; do
    if [[ -f "modules/imgstream/$file" ]]; then
        print_status "SUCCESS" "Found: modules/imgstream/$file"
    else
        print_status "ERROR" "Missing: modules/imgstream/$file"
    fi
done

# Check for sensitive information
print_status "INFO" "Checking for sensitive information..."
SENSITIVE_PATTERNS=(
    "password"
    "secret"
    "key.*="
    "token"
    "credential"
)

for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    if grep -r -i "$pattern" . --exclude-dir=.terraform --exclude="*.tfstate*" > /dev/null 2>&1; then
        print_status "WARNING" "Potential sensitive information found (pattern: $pattern)"
        print_status "INFO" "Please review and ensure no secrets are hardcoded"
    fi
done

# Check for .gitignore
if [[ -f "../.gitignore" ]]; then
    if grep -q "terraform.tfvars" ../.gitignore && grep -q "*.tfstate" ../.gitignore; then
        print_status "SUCCESS" "Terraform files properly ignored in .gitignore"
    else
        print_status "WARNING" "Consider adding terraform.tfvars and *.tfstate to .gitignore"
    fi
else
    print_status "WARNING" ".gitignore not found in parent directory"
fi

print_status "SUCCESS" "Terraform validation completed successfully!"
print_status "INFO" "Next steps:"
echo "  1. Deploy common infrastructure first:"
echo "     ./scripts/deploy.sh -e common -a apply"
echo "  2. Deploy development environment:"
echo "     ./scripts/deploy.sh -e dev -a plan"
echo "     ./scripts/deploy.sh -e dev -a apply"
echo "  3. Deploy production environment:"
echo "     ./scripts/deploy.sh -e prod -a plan"
echo "     ./scripts/deploy.sh -e prod -a apply"
