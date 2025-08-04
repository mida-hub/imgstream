#!/bin/bash

# Complete deployment script for ImgStream infrastructure
# This script deploys common infrastructure first, then dev and prod environments

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

# Default values
PROJECT_ID="apps-466614"
SKIP_COMMON=false
SKIP_DEV=false
SKIP_PROD=false
AUTO_APPROVE=false

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p PROJECT_ID    GCP project ID [default: apps-466614]"
    echo "  --skip-common    Skip common infrastructure deployment"
    echo "  --skip-dev       Skip development environment deployment"
    echo "  --skip-prod      Skip production environment deployment"
    echo "  --auto-approve   Auto-approve all terraform apply operations"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Deploy all environments"
    echo "  $0 --skip-common             # Deploy only dev and prod"
    echo "  $0 --skip-prod --auto-approve # Deploy common and dev with auto-approve"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --skip-common)
            SKIP_COMMON=true
            shift
            ;;
        --skip-dev)
            SKIP_DEV=true
            shift
            ;;
        --skip-prod)
            SKIP_PROD=true
            shift
            ;;
        --auto-approve)
            AUTO_APPROVE=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Check if we're in the correct directory
if [ ! -d "terraform" ]; then
    print_error "terraform directory not found. Please run this script from the project root."
    exit 1
fi

print_header "ImgStream Infrastructure Deployment"
echo "Project ID: $PROJECT_ID"
echo "Skip Common: $SKIP_COMMON"
echo "Skip Dev: $SKIP_DEV"
echo "Skip Prod: $SKIP_PROD"
echo "Auto Approve: $AUTO_APPROVE"
echo ""

# Check prerequisites
print_status "Checking prerequisites..."

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

# Set the project
print_status "Setting GCP project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

# Function to deploy environment
deploy_environment() {
    local env=$1
    local auto_approve_flag=""
    
    if [[ "$AUTO_APPROVE" == "true" ]]; then
        auto_approve_flag="--auto-approve"
    fi
    
    print_header "Deploying $env Environment"
    
    # Use the terraform/scripts/deploy.sh script
    if [[ -f "terraform/scripts/deploy.sh" ]]; then
        bash terraform/scripts/deploy.sh -p "$PROJECT_ID" -e "$env" -a apply $auto_approve_flag
    else
        print_error "terraform/scripts/deploy.sh not found"
        exit 1
    fi
    
    if [[ $? -eq 0 ]]; then
        print_status "$env environment deployed successfully!"
    else
        print_error "$env environment deployment failed!"
        exit 1
    fi
}

# Deploy common infrastructure
if [[ "$SKIP_COMMON" != "true" ]]; then
    deploy_environment "common"
    echo ""
else
    print_warning "Skipping common infrastructure deployment"
fi

# Deploy development environment
if [[ "$SKIP_DEV" != "true" ]]; then
    deploy_environment "dev"
    echo ""
else
    print_warning "Skipping development environment deployment"
fi

# Deploy production environment
if [[ "$SKIP_PROD" != "true" ]]; then
    deploy_environment "prod"
    echo ""
else
    print_warning "Skipping production environment deployment"
fi

print_header "Deployment Complete"
print_status "All selected environments have been deployed successfully!"

# Show outputs
print_header "Getting Deployment Information"

if [[ "$SKIP_COMMON" != "true" ]]; then
    print_status "Common Infrastructure Outputs:"
    cd terraform/common
    terraform output
    cd ../..
    echo ""
fi

if [[ "$SKIP_DEV" != "true" ]]; then
    print_status "Development Environment Outputs:"
    cd terraform/dev
    terraform output
    cd ../..
    echo ""
fi

if [[ "$SKIP_PROD" != "true" ]]; then
    print_status "Production Environment Outputs:"
    cd terraform/prod
    terraform output
    cd ../..
    echo ""
fi

print_status "Deployment completed successfully!"
print_status "Don't forget to configure your GitHub repository secrets with the OIDC outputs."
