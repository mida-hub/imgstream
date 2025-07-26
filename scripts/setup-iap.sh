#!/bin/bash
# Cloud IAP setup script for imgstream

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROJECT_ID=""
ENVIRONMENT="dev"
SUPPORT_EMAIL=""
CUSTOM_DOMAIN=""
ALLOWED_USERS=""
ALLOWED_DOMAINS=""

# Function to display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID -e SUPPORT_EMAIL [-env ENVIRONMENT] [OPTIONS]"
    echo ""
    echo "Required:"
    echo "  -p PROJECT_ID      GCP project ID"
    echo "  -e SUPPORT_EMAIL   Support email for OAuth consent screen"
    echo ""
    echo "Optional:"
    echo "  -env ENVIRONMENT   Environment (dev|prod) [default: dev]"
    echo "  -d CUSTOM_DOMAIN   Custom domain for the application"
    echo "  -u ALLOWED_USERS   Comma-separated list of allowed user emails"
    echo "  -dom ALLOWED_DOMAINS Comma-separated list of allowed domains"
    echo "  -h                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project-id -e support@example.com -env dev"
    echo "  $0 -p my-project-id -e support@example.com -env prod -d imgstream.example.com -u admin@example.com,user@example.com"
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
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -e|--email)
            SUPPORT_EMAIL="$2"
            shift 2
            ;;
        -env|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--domain)
            CUSTOM_DOMAIN="$2"
            shift 2
            ;;
        -u|--users)
            ALLOWED_USERS="$2"
            shift 2
            ;;
        -dom|--domains)
            ALLOWED_DOMAINS="$2"
            shift 2
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

# Validate required parameters
if [[ -z "$PROJECT_ID" ]]; then
    print_error "PROJECT_ID is required"
    usage
fi

if [[ -z "$SUPPORT_EMAIL" ]]; then
    print_error "SUPPORT_EMAIL is required"
    usage
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|prod)$ ]]; then
    print_error "ENVIRONMENT must be 'dev' or 'prod'"
    exit 1
fi

# Display configuration
echo "=================================="
echo "    Cloud IAP Setup Configuration"
echo "=================================="
echo "Project ID:      $PROJECT_ID"
echo "Environment:     $ENVIRONMENT"
echo "Support Email:   $SUPPORT_EMAIL"
echo "Custom Domain:   ${CUSTOM_DOMAIN:-"None (will use load balancer IP)"}"
echo "Allowed Users:   ${ALLOWED_USERS:-"None specified"}"
echo "Allowed Domains: ${ALLOWED_DOMAINS:-"None specified"}"
echo "=================================="
echo ""

# Confirm before proceeding
read -p "Do you want to proceed with this configuration? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Setup cancelled by user"
    exit 0
fi

# Set the project
print_status "Setting GCP project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID" || {
    print_error "Failed to set project. Please check if project exists and you have access."
    exit 1
}

# Enable required APIs
print_status "Enabling required APIs..."
REQUIRED_APIS=(
    "iap.googleapis.com"
    "compute.googleapis.com"
    "run.googleapis.com"
    "storage.googleapis.com"
    "secretmanager.googleapis.com"
    "cloudbuild.googleapis.com"
)

for api in "${REQUIRED_APIS[@]}"; do
    print_status "Enabling $api..."
    gcloud services enable "$api" || {
        print_error "Failed to enable $api"
        exit 1
    }
done

print_success "All required APIs enabled"

# Update Terraform variables file
TFVARS_FILE="terraform/environments/${ENVIRONMENT}.tfvars"

if [[ ! -f "$TFVARS_FILE" ]]; then
    print_error "Terraform variables file not found: $TFVARS_FILE"
    exit 1
fi

print_status "Updating Terraform configuration..."

# Create backup of original file
cp "$TFVARS_FILE" "${TFVARS_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

# Update support email
if grep -q "iap_support_email" "$TFVARS_FILE"; then
    sed -i.tmp "s|iap_support_email = .*|iap_support_email = \"$SUPPORT_EMAIL\"|" "$TFVARS_FILE"
else
    echo "iap_support_email = \"$SUPPORT_EMAIL\"" >> "$TFVARS_FILE"
fi

# Enable IAP for production
if [[ "$ENVIRONMENT" == "prod" ]]; then
    if grep -q "enable_iap" "$TFVARS_FILE"; then
        sed -i.tmp "s|enable_iap = .*|enable_iap = true|" "$TFVARS_FILE"
    else
        echo "enable_iap = true" >> "$TFVARS_FILE"
    fi
fi

# Update custom domain if provided
if [[ -n "$CUSTOM_DOMAIN" ]]; then
    if grep -q "custom_domain" "$TFVARS_FILE"; then
        sed -i.tmp "s|custom_domain = .*|custom_domain = \"$CUSTOM_DOMAIN\"|" "$TFVARS_FILE"
    else
        echo "custom_domain = \"$CUSTOM_DOMAIN\"" >> "$TFVARS_FILE"
    fi
fi

# Update allowed users if provided
if [[ -n "$ALLOWED_USERS" ]]; then
    # Convert comma-separated list to Terraform list format
    IFS=',' read -ra USERS_ARRAY <<< "$ALLOWED_USERS"
    USERS_LIST="["
    for i in "${!USERS_ARRAY[@]}"; do
        if [[ $i -gt 0 ]]; then
            USERS_LIST+=", "
        fi
        USERS_LIST+="\"${USERS_ARRAY[$i]}\""
    done
    USERS_LIST+="]"
    
    if grep -q "allowed_users" "$TFVARS_FILE"; then
        sed -i.tmp "s|allowed_users = .*|allowed_users = $USERS_LIST|" "$TFVARS_FILE"
    else
        echo "allowed_users = $USERS_LIST" >> "$TFVARS_FILE"
    fi
fi

# Update allowed domains if provided
if [[ -n "$ALLOWED_DOMAINS" ]]; then
    # Convert comma-separated list to Terraform list format
    IFS=',' read -ra DOMAINS_ARRAY <<< "$ALLOWED_DOMAINS"
    DOMAINS_LIST="["
    for i in "${!DOMAINS_ARRAY[@]}"; do
        if [[ $i -gt 0 ]]; then
            DOMAINS_LIST+=", "
        fi
        DOMAINS_LIST+="\"${DOMAINS_ARRAY[$i]}\""
    done
    DOMAINS_LIST+="]"
    
    if grep -q "allowed_domains" "$TFVARS_FILE"; then
        sed -i.tmp "s|allowed_domains = .*|allowed_domains = $DOMAINS_LIST|" "$TFVARS_FILE"
    else
        echo "allowed_domains = $DOMAINS_LIST" >> "$TFVARS_FILE"
    fi
fi

# Clean up temporary files
rm -f "${TFVARS_FILE}.tmp"

print_success "Terraform configuration updated"

# Deploy infrastructure with Terraform
print_status "Deploying IAP infrastructure with Terraform..."
cd terraform

# Initialize Terraform
print_status "Initializing Terraform..."
terraform init || {
    print_error "Terraform initialization failed"
    exit 1
}

# Plan the deployment
print_status "Planning Terraform deployment..."
terraform plan -var-file="environments/${ENVIRONMENT}.tfvars" -var="project_id=$PROJECT_ID" || {
    print_error "Terraform planning failed"
    exit 1
}

# Ask for confirmation before applying
echo ""
read -p "Do you want to apply these Terraform changes? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Applying Terraform configuration..."
    terraform apply -var-file="environments/${ENVIRONMENT}.tfvars" -var="project_id=$PROJECT_ID" -auto-approve || {
        print_error "Terraform apply failed"
        exit 1
    }
    
    print_success "Infrastructure deployed successfully"
    
    # Get outputs if IAP is enabled
    if [[ "$ENVIRONMENT" == "prod" ]] || terraform output -raw iap_enabled 2>/dev/null | grep -q "true"; then
        echo ""
        echo "=================================="
        echo "    IAP Setup Complete"
        echo "=================================="
        
        LOAD_BALANCER_IP=$(terraform output -raw load_balancer_ip 2>/dev/null || echo "N/A")
        IAP_CLIENT_ID=$(terraform output -raw iap_client_id 2>/dev/null || echo "N/A")
        APPLICATION_URL=$(terraform output -raw application_url 2>/dev/null || echo "N/A")
        
        echo "Load Balancer IP: $LOAD_BALANCER_IP"
        echo "IAP Client ID:    $IAP_CLIENT_ID"
        echo "Application URL:  $APPLICATION_URL"
        
        if [[ -n "$CUSTOM_DOMAIN" ]]; then
            echo ""
            echo "Next steps for custom domain:"
            echo "1. Create DNS A record: $CUSTOM_DOMAIN -> $LOAD_BALANCER_IP"
            echo "2. Wait for SSL certificate provisioning (may take up to 60 minutes)"
            echo "3. Verify SSL certificate status:"
            echo "   gcloud compute ssl-certificates describe imgstream-${ENVIRONMENT}-ssl-cert --global"
        fi
        
        echo ""
        echo "IAP Access Management:"
        echo "1. Go to: https://console.cloud.google.com/security/iap?project=$PROJECT_ID"
        echo "2. Find your backend service: imgstream-${ENVIRONMENT}-backend"
        echo "3. Add users/groups to the 'IAP-secured Web App User' role"
        
        if [[ -n "$ALLOWED_USERS" ]] || [[ -n "$ALLOWED_DOMAINS" ]]; then
            echo ""
            echo "Configured access has been granted to:"
            [[ -n "$ALLOWED_USERS" ]] && echo "  Users: $ALLOWED_USERS"
            [[ -n "$ALLOWED_DOMAINS" ]] && echo "  Domains: $ALLOWED_DOMAINS"
        fi
    else
        echo ""
        echo "=================================="
        echo "    Development Setup Complete"
        echo "=================================="
        APPLICATION_URL=$(terraform output -raw application_url 2>/dev/null || echo "N/A")
        echo "Application URL: $APPLICATION_URL"
        echo "Note: IAP is disabled for development environment"
    fi
    
else
    print_warning "Terraform deployment cancelled"
fi

cd ..

echo ""
print_success "Setup complete!"
echo ""
echo "To test your setup, run:"
echo "  ./scripts/test-iap.sh -p $PROJECT_ID -env $ENVIRONMENT"
