#!/bin/bash

# Terraform deployment script for imgstream (new modular structure)
set -e

# Default values
ENVIRONMENT="dev"
ACTION="plan"
PROJECT_ID="apps-466614"
AUTO_APPROVE=false

# Function to display usage
usage() {
    echo "Usage: $0 [-p PROJECT_ID] [-e ENVIRONMENT] [-a ACTION] [--auto-approve]"
    echo ""
    echo "Options:"
    echo "  -p PROJECT_ID    GCP project ID [default: apps-466614]"
    echo "  -e ENVIRONMENT   Environment (common|dev|prod) [default: dev]"
    echo "  -a ACTION        Terraform action (plan|apply|destroy) [default: plan]"
    echo "  --auto-approve   Auto-approve terraform apply/destroy"
    echo "  -h               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -e common -a apply                    # Deploy common infrastructure"
    echo "  $0 -e dev -a plan                        # Plan dev environment"
    echo "  $0 -e prod -a apply --auto-approve       # Apply prod environment"
    echo ""
    echo "IMPORTANT: Deploy 'common' first, then 'dev' and 'prod'"
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

# Validate parameters
if [[ ! "$ENVIRONMENT" =~ ^(common|dev|prod)$ ]]; then
    echo "Error: ENVIRONMENT must be 'common', 'dev', or 'prod'"
    exit 1
fi

if [[ ! "$ACTION" =~ ^(plan|apply|destroy)$ ]]; then
    echo "Error: ACTION must be 'plan', 'apply', or 'destroy'"
    exit 1
fi

# Set working directory to specific terraform environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$TERRAFORM_ROOT/$ENVIRONMENT"

if [[ ! -d "$TERRAFORM_DIR" ]]; then
    echo "Error: Terraform directory not found: $TERRAFORM_DIR"
    exit 1
fi

cd "$TERRAFORM_DIR"

echo "=== Terraform Deployment (New Modular Structure) ==="
echo "Project ID: $PROJECT_ID"
echo "Environment: $ENVIRONMENT"
echo "Action: $ACTION"
echo "Working Directory: $TERRAFORM_DIR"
echo ""

# Check if common infrastructure is deployed (for dev/prod environments)
if [[ "$ENVIRONMENT" != "common" ]]; then
    echo "Checking if common infrastructure is deployed..."
    COMMON_STATE_BUCKET="apps-466614-terraform-state"
    if gsutil ls "gs://$COMMON_STATE_BUCKET/common/" > /dev/null 2>&1; then
        echo "✓ Common infrastructure state found"
    else
        echo "⚠ Common infrastructure not found. Please deploy 'common' first:"
        echo "  $0 -e common -a apply"
        exit 1
    fi
fi

# Check if required APIs are enabled
echo "Checking required APIs..."
REQUIRED_APIS=(
    "run.googleapis.com"
    "storage.googleapis.com"
    "artifactregistry.googleapis.com"
    "iam.googleapis.com"
    "compute.googleapis.com"
    "monitoring.googleapis.com"
    "logging.googleapis.com"
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

# Prepare var-file arguments
VAR_FILE_ARGS=""
if [[ "$ENVIRONMENT" != "common" ]]; then
    VAR_FILE_ARGS="-var-file=${ENVIRONMENT}.tfvars"
    
    # Add local tfvars file if it exists
    if [[ -f "terraform.tfvars.local" ]]; then
        echo "Found terraform.tfvars.local, including in deployment..."
        VAR_FILE_ARGS="$VAR_FILE_ARGS -var-file=terraform.tfvars.local"
    fi
fi

# Run Terraform command based on environment
case $ACTION in
    plan)
        echo "Running Terraform plan for $ENVIRONMENT..."
        if [[ "$ENVIRONMENT" == "common" ]]; then
            terraform plan
        else
            terraform plan $VAR_FILE_ARGS
        fi
        ;;
    apply)
        echo "Running Terraform apply for $ENVIRONMENT..."
        if [[ "$ENVIRONMENT" == "common" ]]; then
            if [[ "$AUTO_APPROVE" == "true" ]]; then
                terraform apply -auto-approve
            else
                terraform apply
            fi
        else
            if [[ "$AUTO_APPROVE" == "true" ]]; then
                terraform apply $VAR_FILE_ARGS -auto-approve
            else
                terraform apply $VAR_FILE_ARGS
            fi
        fi
        ;;
    destroy)
        echo "Running Terraform destroy for $ENVIRONMENT..."
        if [[ "$ENVIRONMENT" == "common" ]]; then
            echo "WARNING: Destroying common infrastructure will affect all environments!"
            echo -n "Are you sure? (type 'yes' to confirm): "
            read -r CONFIRM_DESTROY
            if [[ "$CONFIRM_DESTROY" == "yes" ]]; then
                if [[ "$AUTO_APPROVE" == "true" ]]; then
                    terraform destroy -auto-approve
                else
                    terraform destroy
                fi
            else
                echo "Destroy cancelled."
                exit 1
            fi
        else
            if [[ "$AUTO_APPROVE" == "true" ]]; then
                terraform destroy $VAR_FILE_ARGS -auto-approve
            else
                terraform destroy $VAR_FILE_ARGS
            fi
        fi
        ;;
esac

echo ""
echo "=== Deployment Complete ==="
