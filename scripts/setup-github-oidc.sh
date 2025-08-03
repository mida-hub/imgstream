#!/bin/bash

# Setup script for GitHub Actions OIDC authentication with Google Cloud
# This script helps configure the necessary Terraform variables and provides
# instructions for setting up GitHub repository secrets.

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

# Display authentication setup instructions
show_auth_instructions() {
    print_header "Authentication Setup Required"
    echo ""
    print_status "To use this script, you need to authenticate with Google Cloud:"
    echo ""
    echo "1. Authenticate your user account:"
    echo "   gcloud auth login"
    echo ""
    echo "2. Set up Application Default Credentials:"
    echo "   gcloud auth application-default login"
    echo ""
    echo "3. Set your default project:"
    echo "   gcloud config set project YOUR_PROJECT_ID"
    echo ""
    print_warning "After completing these steps, run this script again."
    echo ""
}

# Check if required tools are installed
check_requirements() {
    print_header "Checking Requirements"
    
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed. Please install Terraform first."
        exit 1
    fi
    
    if ! command -v gcloud &> /dev/null; then
        print_error "Google Cloud CLI is not installed. Please install gcloud first."
        exit 1
    fi
    
    print_status "All required tools are installed."
}

# Get project information
get_project_info() {
    print_header "Project Information"
    
    # Check if user is authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null 2>&1; then
        print_error "You are not authenticated with Google Cloud."
        show_auth_instructions
        exit 1
    fi
    
    # Check if Application Default Credentials are set
    if ! gcloud auth application-default print-access-token > /dev/null 2>&1; then
        print_error "Application Default Credentials are not set."
        echo ""
        print_status "Please run the following command to set up Application Default Credentials:"
        echo "   gcloud auth application-default login"
        echo ""
        print_warning "This is required for Terraform to authenticate with Google Cloud."
        exit 1
    fi
    
    print_status "Google Cloud authentication verified."
    
    # Get current project
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
    
    if [ -z "$CURRENT_PROJECT" ]; then
        print_error "No Google Cloud project is set. Please run 'gcloud config set project PROJECT_ID'"
        exit 1
    fi
    
    print_status "Current Google Cloud project: $CURRENT_PROJECT"
    
    # Get GitHub repository
    if [ -d ".git" ]; then
        GITHUB_REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*github\.com[:/]\([^/]*\/[^/]*\)\.git.*/\1/' || echo "")
        if [ -n "$GITHUB_REPO" ]; then
            print_status "Detected GitHub repository: $GITHUB_REPO"
        fi
    fi
    
    if [ -z "$GITHUB_REPO" ]; then
        print_warning "Could not detect GitHub repository. You'll need to set this manually."
        echo -n "Please enter your GitHub repository (format: owner/repo): "
        read GITHUB_REPO
    fi
    
    export PROJECT_ID="$CURRENT_PROJECT"
    export GITHUB_REPOSITORY="$GITHUB_REPO"
}

# Update Terraform variables
update_terraform_vars() {
    print_header "Updating Terraform Variables"
    
    # Update terraform.tfvars.example
    if [ -f "terraform/terraform.tfvars.example" ]; then
        sed -i.bak "s|github_repository = \".*\"|github_repository = \"$GITHUB_REPOSITORY\"|" terraform/terraform.tfvars.example
        print_status "Updated terraform/terraform.tfvars.example"
    fi
    
    # Update prod.tfvars
    if [ -f "terraform/environments/prod.tfvars" ]; then
        sed -i.bak "s|github_repository = \".*\"|github_repository = \"$GITHUB_REPOSITORY\"|" terraform/environments/prod.tfvars
        print_status "Updated terraform/environments/prod.tfvars"
    fi
    
    # Create or update terraform.tfvars if it doesn't exist
    if [ ! -f "terraform/terraform.tfvars" ]; then
        print_status "Creating terraform/terraform.tfvars from example..."
        cp terraform/terraform.tfvars.example terraform/terraform.tfvars
        
        # Update project_id in terraform.tfvars
        sed -i.bak "s|project_id = \".*\"|project_id = \"$PROJECT_ID\"|" terraform/terraform.tfvars
        sed -i.bak "s|github_repository = \".*\"|github_repository = \"$GITHUB_REPOSITORY\"|" terraform/terraform.tfvars
        
        print_warning "Please review and update terraform/terraform.tfvars with your specific configuration."
    fi
}

# Apply Terraform configuration
apply_terraform() {
    print_header "Applying Terraform Configuration"
    
    # Verify authentication before proceeding
    if ! gcloud auth application-default print-access-token > /dev/null 2>&1; then
        print_error "Application Default Credentials are not available."
        print_error "Please run: gcloud auth application-default login"
        exit 1
    fi
    
    cd terraform
    
    print_status "Initializing Terraform..."
    terraform init
    
    print_status "Planning Terraform changes..."
    terraform plan -target=google_iam_workload_identity_pool.github_actions \
                   -target=google_iam_workload_identity_pool_provider.github_actions \
                   -target=google_service_account.github_actions \
                   -target=google_service_account_iam_binding.github_actions_workload_identity \
                   -target=google_project_iam_member.github_actions_roles
    
    echo -n "Do you want to apply these changes? (y/N): "
    read -r CONFIRM
    
    if [[ $CONFIRM =~ ^[Yy]$ ]]; then
        print_status "Applying Terraform changes..."
        terraform apply -target=google_iam_workload_identity_pool.github_actions \
                       -target=google_iam_workload_identity_pool_provider.github_actions \
                       -target=google_service_account.github_actions \
                       -target=google_service_account_iam_binding.github_actions_workload_identity \
                       -target=google_project_iam_member.github_actions_roles \
                       -auto-approve
        
        print_status "Terraform configuration applied successfully!"
    else
        print_warning "Terraform apply skipped. You can run it manually later."
    fi
    
    cd ..
}

# Get Terraform outputs
get_terraform_outputs() {
    print_header "Getting Terraform Outputs"
    
    cd terraform
    
    WIF_PROVIDER=$(terraform output -raw workload_identity_provider 2>/dev/null || echo "")
    SERVICE_ACCOUNT=$(terraform output -raw github_actions_service_account_email 2>/dev/null || echo "")
    
    cd ..
    
    if [ -n "$WIF_PROVIDER" ] && [ -n "$SERVICE_ACCOUNT" ]; then
        print_status "Terraform outputs retrieved successfully!"
        export WIF_PROVIDER
        export SERVICE_ACCOUNT
    else
        print_error "Could not retrieve Terraform outputs. Make sure Terraform has been applied."
        exit 1
    fi
}

# Display GitHub secrets configuration
display_github_secrets() {
    print_header "GitHub Repository Secrets Configuration"
    
    echo ""
    print_status "Please add the following secrets to your GitHub repository:"
    echo ""
    echo "Repository: https://github.com/$GITHUB_REPOSITORY/settings/secrets/actions"
    echo ""
    echo "Required secrets:"
    echo "  WIF_PROVIDER: $WIF_PROVIDER"
    echo "  WIF_SERVICE_ACCOUNT: $SERVICE_ACCOUNT"
    echo "  GCP_PROJECT_ID: $PROJECT_ID"
    echo ""
    print_warning "Remove the old GCP_SA_KEY secret as it's no longer needed."
    echo ""
    
    # Additional secrets that might be needed
    echo "Additional secrets you may need to configure:"
    echo "  GCS_BUCKET_DEV: your-dev-bucket-name"
    echo "  GCS_BUCKET_PROD: your-prod-bucket-name"
    echo "  PROD_DOMAIN_URL: https://your-production-domain.com"
    echo ""
}

# Main execution
main() {
    print_header "GitHub Actions OIDC Setup for Google Cloud"
    echo ""
    
    check_requirements
    get_project_info
    update_terraform_vars
    apply_terraform
    get_terraform_outputs
    display_github_secrets
    
    print_header "Setup Complete"
    print_status "OIDC authentication has been configured successfully!"
    print_status "Don't forget to update your GitHub repository secrets."
    echo ""
    print_warning "After updating GitHub secrets, test the workflow to ensure everything works correctly."
}

# Run main function
main "$@"
