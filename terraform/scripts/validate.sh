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
TERRAFORM_DIR="$(dirname "$SCRIPT_DIR")"
cd "$TERRAFORM_DIR"

print_status "INFO" "Starting Terraform validation..."
print_status "INFO" "Working Directory: $TERRAFORM_DIR"

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

# Initialize Terraform
print_status "INFO" "Initializing Terraform..."
if terraform init -backend=false > /dev/null 2>&1; then
    print_status "SUCCESS" "Terraform initialized successfully"
else
    print_status "ERROR" "Terraform initialization failed"
    exit 1
fi

# Validate Terraform configuration
print_status "INFO" "Validating Terraform configuration..."
if terraform validate > /dev/null 2>&1; then
    print_status "SUCCESS" "Terraform configuration is valid"
else
    print_status "ERROR" "Terraform configuration validation failed"
    terraform validate
    exit 1
fi

# Format check
print_status "INFO" "Checking Terraform formatting..."
if terraform fmt -check -recursive > /dev/null 2>&1; then
    print_status "SUCCESS" "Terraform files are properly formatted"
else
    print_status "WARNING" "Some Terraform files need formatting"
    print_status "INFO" "Run 'terraform fmt -recursive' to fix formatting"
fi

# Check for required files
REQUIRED_FILES=(
    "main.tf"
    "variables.tf"
    "outputs.tf"
    "storage.tf"
    "security.tf"
    "terraform.tfvars.example"
    "environments/dev.tfvars"
    "environments/prod.tfvars"
)

print_status "INFO" "Checking for required files..."
for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        print_status "SUCCESS" "Found: $file"
    else
        print_status "ERROR" "Missing: $file"
        exit 1
    fi
done

# Check terraform.tfvars
if [[ -f "terraform.tfvars" ]]; then
    print_status "SUCCESS" "Found: terraform.tfvars"
    
    # Check if project_id is set
    if grep -q "project_id.*=.*\"your-gcp-project-id\"" terraform.tfvars; then
        print_status "WARNING" "terraform.tfvars still contains example project_id"
        print_status "INFO" "Please update terraform.tfvars with your actual project ID"
    else
        print_status "SUCCESS" "terraform.tfvars appears to be configured"
    fi
else
    print_status "WARNING" "terraform.tfvars not found"
    print_status "INFO" "Copy terraform.tfvars.example to terraform.tfvars and configure it"
fi

# Validate environment files
print_status "INFO" "Validating environment files..."
for env in "dev" "prod"; do
    env_file="environments/${env}.tfvars"
    if [[ -f "$env_file" ]]; then
        # Basic syntax check
        if terraform validate -var-file="$env_file" -var="project_id=test-project" > /dev/null 2>&1; then
            print_status "SUCCESS" "Environment file $env_file is valid"
        else
            print_status "ERROR" "Environment file $env_file has syntax errors"
        fi
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
echo "  1. Configure terraform.tfvars with your project settings"
echo "  2. Run: ./scripts/deploy.sh -p YOUR_PROJECT_ID -e dev -a plan"
echo "  3. Review the plan and apply: ./scripts/deploy.sh -p YOUR_PROJECT_ID -e dev -a apply"
