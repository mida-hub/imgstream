#!/bin/bash

# Terraform initialization script with environment-specific backend configuration
# Usage: ./scripts/terraform-init.sh [dev|prod]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Check if environment is provided
if [ $# -eq 0 ]; then
    print_error "Environment not specified"
    echo "Usage: $0 [dev|prod]"
    echo ""
    echo "Examples:"
    echo "  $0 dev   # Initialize for development environment"
    echo "  $0 prod  # Initialize for production environment"
    exit 1
fi

ENVIRONMENT=$1

# Validate environment
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    print_error "Invalid environment: $ENVIRONMENT"
    echo "Supported environments: dev, prod"
    exit 1
fi

print_header "Terraform Initialization for $ENVIRONMENT Environment"

# Check if we're in the correct directory
if [ ! -f "terraform/main.tf" ]; then
    print_error "terraform/main.tf not found. Please run this script from the project root."
    exit 1
fi

# Check if backend config file exists
BACKEND_CONFIG="terraform/backend-${ENVIRONMENT}.hcl"
if [ ! -f "$BACKEND_CONFIG" ]; then
    print_error "Backend configuration file not found: $BACKEND_CONFIG"
    exit 1
fi

# Check if required tools are installed
print_status "Checking requirements..."

if ! command -v terraform &> /dev/null; then
    print_error "Terraform is not installed. Please install Terraform first."
    exit 1
fi

if ! command -v gcloud &> /dev/null; then
    print_error "Google Cloud CLI is not installed. Please install gcloud first."
    exit 1
fi

# Check if authenticated to Google Cloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null; then
    print_error "Not authenticated to Google Cloud. Please run 'gcloud auth login'"
    exit 1
fi

# Get current project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -z "$CURRENT_PROJECT" ]; then
    print_error "No Google Cloud project is set. Please run 'gcloud config set project PROJECT_ID'"
    exit 1
fi

print_status "Current Google Cloud project: $CURRENT_PROJECT"

# Check if the Terraform state bucket exists
BUCKET_NAME="tfstate-apps-466614"
print_status "Checking if Terraform state bucket exists: gs://$BUCKET_NAME"

if ! gsutil ls "gs://$BUCKET_NAME" > /dev/null 2>&1; then
    print_warning "Terraform state bucket does not exist: gs://$BUCKET_NAME"
    echo -n "Do you want to create it? (y/N): "
    read -r CREATE_BUCKET
    
    if [[ $CREATE_BUCKET =~ ^[Yy]$ ]]; then
        print_status "Creating Terraform state bucket..."
        gsutil mb -p "$CURRENT_PROJECT" -c STANDARD -l asia-northeast1 "gs://$BUCKET_NAME"
        
        # Enable versioning for state file protection
        gsutil versioning set on "gs://$BUCKET_NAME"
        
        print_status "Bucket created successfully with versioning enabled"
    else
        print_error "Cannot proceed without the Terraform state bucket"
        exit 1
    fi
else
    print_status "Terraform state bucket exists"
fi

# Change to terraform directory
cd terraform

# Remove existing .terraform directory if it exists (for backend migration)
if [ -d ".terraform" ]; then
    print_warning "Existing .terraform directory found. Removing for clean initialization..."
    rm -rf .terraform
fi

# Initialize Terraform with environment-specific backend
print_status "Initializing Terraform with $ENVIRONMENT backend configuration..."

# Use gcloud access token for authentication
export GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)
terraform init -backend-config="backend-${ENVIRONMENT}.hcl"

if [ $? -eq 0 ]; then
    print_status "Terraform initialized successfully for $ENVIRONMENT environment"
    
    # Show backend configuration
    print_header "Backend Configuration"
    echo "Bucket: gs://$BUCKET_NAME"
    echo "Prefix: imgstream/$ENVIRONMENT"
    echo "State file: gs://$BUCKET_NAME/imgstream/$ENVIRONMENT/default.tfstate"
    
    # Validate configuration
    print_status "Validating Terraform configuration..."
    GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token) terraform validate
    
    if [ $? -eq 0 ]; then
        print_status "Terraform configuration is valid"
        
        # Show workspace info
        print_header "Workspace Information"
        GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token) terraform workspace show
        
        echo ""
        print_status "Terraform is ready for $ENVIRONMENT environment!"
        echo ""
        echo "Next steps:"
        echo "  terraform plan -var-file=environments/${ENVIRONMENT}.tfvars"
        echo "  terraform apply -var-file=environments/${ENVIRONMENT}.tfvars"
    else
        print_error "Terraform configuration validation failed"
        exit 1
    fi
else
    print_error "Terraform initialization failed"
    exit 1
fi
