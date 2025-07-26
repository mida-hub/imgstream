#!/bin/bash

# Terraform deployment script for imgstream
set -e

# Default values
ENVIRONMENT="dev"
ACTION="plan"
PROJECT_ID=""
AUTO_APPROVE=false

# Function to display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID [-e ENVIRONMENT] [-a ACTION] [--auto-approve]"
    echo ""
    echo "Options:"
    echo "  -p PROJECT_ID    GCP project ID (required)"
    echo "  -e ENVIRONMENT   Environment (dev|prod) [default: dev]"
    echo "  -a ACTION        Terraform action (plan|apply|destroy) [default: plan]"
    echo "  --auto-approve   Auto-approve terraform apply/destroy"
    echo "  -h               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project-id -e dev -a plan"
    echo "  $0 -p my-project-id -e prod -a apply --auto-approve"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
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

# Validate required parameters
if [[ -z "$PROJECT_ID" ]]; then
    echo "Error: PROJECT_ID is required"
    usage
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|prod)$ ]]; then
    echo "Error: ENVIRONMENT must be 'dev' or 'prod'"
    exit 1
fi

if [[ ! "$ACTION" =~ ^(plan|apply|destroy)$ ]]; then
    echo "Error: ACTION must be 'plan', 'apply', or 'destroy'"
    exit 1
fi

# Set working directory to terraform root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$(dirname "$SCRIPT_DIR")"
cd "$TERRAFORM_DIR"

echo "=== Terraform Deployment ==="
echo "Project ID: $PROJECT_ID"
echo "Environment: $ENVIRONMENT"
echo "Action: $ACTION"
echo "Working Directory: $TERRAFORM_DIR"
echo ""

# Check if required APIs are enabled
echo "Checking required APIs..."
REQUIRED_APIS=(
    "run.googleapis.com"
    "storage.googleapis.com"
    "secretmanager.googleapis.com"
    "cloudbuild.googleapis.com"
    "containerregistry.googleapis.com"
)

for api in "${REQUIRED_APIS[@]}"; do
    if gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
        echo "✓ $api is enabled"
    else
        echo "⚠ $api is not enabled. Enabling..."
        gcloud services enable "$api"
    fi
done
echo ""

# Check if terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "Error: Terraform is not installed"
    exit 1
fi

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI is not installed"
    exit 1
fi

# Verify gcloud authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "Error: No active gcloud authentication found"
    echo "Please run: gcloud auth login"
    exit 1
fi

# Set the project
echo "Setting GCP project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

# Initialize Terraform
echo "Initializing Terraform..."
terraform init

# Validate Terraform configuration
echo "Validating Terraform configuration..."
terraform validate

# Format Terraform files
terraform fmt -recursive

# Create terraform.tfvars if it doesn't exist
if [[ ! -f "terraform.tfvars" ]]; then
    echo "Creating terraform.tfvars from example..."
    cp terraform.tfvars.example terraform.tfvars
    echo "Please edit terraform.tfvars with your project-specific values"
    echo "Setting project_id to $PROJECT_ID in terraform.tfvars"
    sed -i.bak "s/your-gcp-project-id/$PROJECT_ID/g" terraform.tfvars
fi

# Run Terraform command
case $ACTION in
    plan)
        echo "Running Terraform plan..."
        terraform plan -var-file="environments/${ENVIRONMENT}.tfvars" -var="project_id=$PROJECT_ID"
        ;;
    apply)
        echo "Running Terraform apply..."
        if [[ "$AUTO_APPROVE" == "true" ]]; then
            terraform apply -var-file="environments/${ENVIRONMENT}.tfvars" -var="project_id=$PROJECT_ID" -auto-approve
        else
            terraform apply -var-file="environments/${ENVIRONMENT}.tfvars" -var="project_id=$PROJECT_ID"
        fi
        ;;
    destroy)
        echo "Running Terraform destroy..."
        if [[ "$AUTO_APPROVE" == "true" ]]; then
            terraform destroy -var-file="environments/${ENVIRONMENT}.tfvars" -var="project_id=$PROJECT_ID" -auto-approve
        else
            terraform destroy -var-file="environments/${ENVIRONMENT}.tfvars" -var="project_id=$PROJECT_ID"
        fi
        ;;
esac

echo ""
echo "=== Deployment Complete ==="
