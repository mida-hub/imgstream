#!/bin/bash
# Cloud IAP testing script for imgstream

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
TEST_USER=""

# Function to display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID [-env ENVIRONMENT] [-u TEST_USER]"
    echo ""
    echo "Options:"
    echo "  -p PROJECT_ID    GCP project ID (required)"
    echo "  -env ENVIRONMENT Environment (dev|prod) [default: dev]"
    echo "  -u TEST_USER     Test user email for access verification"
    echo "  -h               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project-id -env dev"
    echo "  $0 -p my-project-id -env prod -u test@example.com"
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
        -env|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -u|--user)
            TEST_USER="$2"
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

echo "=================================="
echo "    Cloud IAP Testing"
echo "=================================="
echo "Project ID:   $PROJECT_ID"
echo "Environment:  $ENVIRONMENT"
echo "Test User:    ${TEST_USER:-"Current authenticated user"}"
echo "=================================="
echo ""

# Set the project
print_status "Setting GCP project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID" || {
    print_error "Failed to set project. Please check if project exists and you have access."
    exit 1
}

# Check if Terraform state exists
if [[ ! -f "terraform/terraform.tfstate" ]]; then
    print_warning "Terraform state not found. Make sure infrastructure is deployed."
    exit 1
fi

cd terraform

# Get Terraform outputs
print_status "Getting infrastructure information..."
IAP_ENABLED=$(terraform output -raw iap_enabled 2>/dev/null || echo "false")
APPLICATION_URL=$(terraform output -raw application_url 2>/dev/null || echo "")
CLOUD_RUN_URL=$(terraform output -raw cloud_run_service_url 2>/dev/null || echo "")

if [[ "$IAP_ENABLED" == "true" ]]; then
    print_status "IAP is enabled for this environment"
    
    # Get IAP-specific information
    LOAD_BALANCER_IP=$(terraform output -raw load_balancer_ip 2>/dev/null || echo "")
    BACKEND_SERVICE=$(terraform output -raw backend_service_name 2>/dev/null || echo "")
    IAP_CLIENT_ID=$(terraform output -raw iap_client_id 2>/dev/null || echo "")
    
    echo "Load Balancer IP:  $LOAD_BALANCER_IP"
    echo "Backend Service:   $BACKEND_SERVICE"
    echo "IAP Client ID:     ${IAP_CLIENT_ID:0:20}..."
    echo "Application URL:   $APPLICATION_URL"
    
    # Test IAP configuration
    print_status "Testing IAP configuration..."
    
    # Check if backend service exists
    if gcloud compute backend-services describe "$BACKEND_SERVICE" --global >/dev/null 2>&1; then
        print_success "Backend service exists: $BACKEND_SERVICE"
        
        # Check IAP status
        IAP_STATUS=$(gcloud compute backend-services describe "$BACKEND_SERVICE" --global --format="value(iap.enabled)" 2>/dev/null || echo "false")
        if [[ "$IAP_STATUS" == "True" ]]; then
            print_success "IAP is enabled on backend service"
        else
            print_error "IAP is not enabled on backend service"
        fi
        
        # Check OAuth client
        OAUTH_CLIENT=$(gcloud compute backend-services describe "$BACKEND_SERVICE" --global --format="value(iap.oauth2ClientId)" 2>/dev/null || echo "")
        if [[ -n "$OAUTH_CLIENT" ]]; then
            print_success "OAuth client is configured"
        else
            print_error "OAuth client is not configured"
        fi
        
    else
        print_error "Backend service not found: $BACKEND_SERVICE"
    fi
    
    # Test access permissions
    print_status "Testing access permissions..."
    
    if [[ -n "$TEST_USER" ]]; then
        print_status "Checking access for user: $TEST_USER"
        
        # Check IAP access
        if gcloud iap web backend-services get-iam-policy "$BACKEND_SERVICE" --format="value(bindings[?role=='roles/iap.httpsResourceAccessor'].members[].flatten())" 2>/dev/null | grep -q "user:$TEST_USER"; then
            print_success "User $TEST_USER has IAP access"
        else
            print_warning "User $TEST_USER does not have IAP access"
            echo "To grant access, run:"
            echo "gcloud iap web backend-services add-iam-policy-binding $BACKEND_SERVICE --member=\"user:$TEST_USER\" --role=\"roles/iap.httpsResourceAccessor\""
        fi
    else
        # Check current user
        CURRENT_USER=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || echo "unknown")
        print_status "Checking access for current user: $CURRENT_USER"
        
        if [[ "$CURRENT_USER" != "unknown" ]]; then
            if gcloud iap web backend-services get-iam-policy "$BACKEND_SERVICE" --format="value(bindings[?role=='roles/iap.httpsResourceAccessor'].members[].flatten())" 2>/dev/null | grep -q "user:$CURRENT_USER"; then
                print_success "Current user has IAP access"
            else
                print_warning "Current user does not have IAP access"
                echo "To grant access, run:"
                echo "gcloud iap web backend-services add-iam-policy-binding $BACKEND_SERVICE --member=\"user:$CURRENT_USER\" --role=\"roles/iap.httpsResourceAccessor\""
            fi
        fi
    fi
    
    # Test SSL certificate (if custom domain)
    if terraform output custom_domain >/dev/null 2>&1; then
        CUSTOM_DOMAIN=$(terraform output -raw custom_domain 2>/dev/null || echo "")
        if [[ -n "$CUSTOM_DOMAIN" ]]; then
            print_status "Testing SSL certificate for custom domain: $CUSTOM_DOMAIN"
            
            SSL_CERT_NAME=$(terraform output -raw ssl_certificate_name 2>/dev/null || echo "")
            if [[ -n "$SSL_CERT_NAME" ]]; then
                SSL_STATUS=$(gcloud compute ssl-certificates describe "$SSL_CERT_NAME" --global --format="value(managed.status)" 2>/dev/null || echo "NOT_FOUND")
                case $SSL_STATUS in
                    "ACTIVE")
                        print_success "SSL certificate is active"
                        ;;
                    "PROVISIONING")
                        print_warning "SSL certificate is still provisioning (this can take up to 60 minutes)"
                        ;;
                    "FAILED_NOT_VISIBLE")
                        print_error "SSL certificate provisioning failed - domain not visible"
                        echo "Check DNS configuration: $CUSTOM_DOMAIN -> $LOAD_BALANCER_IP"
                        ;;
                    *)
                        print_warning "SSL certificate status: $SSL_STATUS"
                        ;;
                esac
            fi
        fi
    fi
    
else
    print_status "IAP is disabled for this environment"
    echo "Cloud Run URL:     $CLOUD_RUN_URL"
    echo "Application URL:   $APPLICATION_URL"
fi

# Test HTTP connectivity
print_status "Testing HTTP connectivity..."
if [[ -n "$APPLICATION_URL" ]]; then
    print_status "Testing connection to: $APPLICATION_URL"
    
    # Use curl to test the endpoint
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$APPLICATION_URL" --max-time 10 --connect-timeout 5 2>/dev/null || echo "000")
    
    case $HTTP_STATUS in
        200)
            print_success "Application is accessible (HTTP 200)"
            ;;
        302|301)
            if [[ "$IAP_ENABLED" == "true" ]]; then
                print_success "Application is redirecting to IAP login (HTTP $HTTP_STATUS)"
            else
                print_warning "Application is redirecting (HTTP $HTTP_STATUS)"
            fi
            ;;
        403)
            if [[ "$IAP_ENABLED" == "true" ]]; then
                print_warning "Access forbidden - check IAP permissions (HTTP 403)"
            else
                print_error "Access forbidden (HTTP 403)"
            fi
            ;;
        404)
            print_error "Application not found (HTTP 404) - check deployment"
            ;;
        502|503)
            print_error "Application unavailable (HTTP $HTTP_STATUS) - check Cloud Run service"
            ;;
        000)
            print_error "Connection failed - check network connectivity and URL"
            ;;
        *)
            print_warning "Unexpected HTTP status: $HTTP_STATUS"
            ;;
    esac
else
    print_error "Application URL not found in Terraform outputs"
fi

cd ..

echo ""
echo "=================================="
echo "    Test Summary"
echo "=================================="
echo "Environment:      $ENVIRONMENT"
echo "IAP Enabled:      $IAP_ENABLED"
echo "Application URL:  ${APPLICATION_URL:-"N/A"}"
echo "HTTP Status:      ${HTTP_STATUS:-"N/A"}"
echo "=================================="
echo ""

if [[ "$IAP_ENABLED" == "true" ]]; then
    echo "Next steps:"
    echo "1. Open $APPLICATION_URL in your browser"
    echo "2. Sign in with your Google account"
    echo "3. Verify you can access the application"
    echo ""
    echo "IAP Management Console:"
    echo "https://console.cloud.google.com/security/iap?project=$PROJECT_ID"
else
    echo "Development environment - no IAP configuration needed"
    echo "Application should be directly accessible at: $APPLICATION_URL"
fi
