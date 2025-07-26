#!/bin/bash
# Cloud Run deployment script for imgstream

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
IMAGE_TAG=""
REGION="us-central1"
SERVICE_NAME=""
FORCE_DEPLOY=false
DRY_RUN=false

# Function to display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID -e ENVIRONMENT -i IMAGE_TAG [OPTIONS]"
    echo ""
    echo "Required:"
    echo "  -p PROJECT_ID    GCP project ID"
    echo "  -e ENVIRONMENT   Environment (dev|prod)"
    echo "  -i IMAGE_TAG     Docker image tag to deploy"
    echo ""
    echo "Optional:"
    echo "  -r REGION        GCP region [default: us-central1]"
    echo "  -s SERVICE_NAME  Cloud Run service name [default: imgstream-{env}]"
    echo "  -f               Force deployment without confirmation"
    echo "  --dry-run        Show deployment command without executing"
    echo "  -h               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project -e dev -i gcr.io/my-project/imgstream:latest"
    echo "  $0 -p my-project -e prod -i gcr.io/my-project/imgstream:v1.0.0 -f"
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
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -i|--image)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_DEPLOY=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
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

if [[ -z "$ENVIRONMENT" ]]; then
    print_error "ENVIRONMENT is required"
    usage
fi

if [[ -z "$IMAGE_TAG" ]]; then
    print_error "IMAGE_TAG is required"
    usage
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|prod)$ ]]; then
    print_error "ENVIRONMENT must be 'dev' or 'prod'"
    exit 1
fi

# Set default service name if not provided
if [[ -z "$SERVICE_NAME" ]]; then
    SERVICE_NAME="imgstream-${ENVIRONMENT}"
fi

# Display configuration
echo "=================================="
echo "    Cloud Run Deployment"
echo "=================================="
echo "Project ID:      $PROJECT_ID"
echo "Environment:     $ENVIRONMENT"
echo "Service Name:    $SERVICE_NAME"
echo "Image Tag:       $IMAGE_TAG"
echo "Region:          $REGION"
echo "Force Deploy:    $FORCE_DEPLOY"
echo "Dry Run:         $DRY_RUN"
echo "=================================="
echo ""

# Set the project
print_status "Setting GCP project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID" || {
    print_error "Failed to set project. Please check if project exists and you have access."
    exit 1
}

# Check if image exists
print_status "Checking if Docker image exists..."
if ! gcloud container images describe "$IMAGE_TAG" >/dev/null 2>&1; then
    print_error "Docker image not found: $IMAGE_TAG"
    print_error "Please build and push the image first"
    exit 1
fi

print_success "Docker image found: $IMAGE_TAG"

# Environment-specific configuration
if [[ "$ENVIRONMENT" == "dev" ]]; then
    ALLOW_UNAUTHENTICATED="--allow-unauthenticated"
    MIN_INSTANCES=0
    MAX_INSTANCES=3
    MEMORY="1Gi"
    CPU=1
    CONCURRENCY=80
elif [[ "$ENVIRONMENT" == "prod" ]]; then
    ALLOW_UNAUTHENTICATED="--no-allow-unauthenticated"
    MIN_INSTANCES=1
    MAX_INSTANCES=10
    MEMORY="2Gi"
    CPU=1
    CONCURRENCY=80
fi

# Build deployment command
DEPLOY_CMD="gcloud run deploy $SERVICE_NAME \
  --image=$IMAGE_TAG \
  --platform=managed \
  --region=$REGION \
  $ALLOW_UNAUTHENTICATED \
  --memory=$MEMORY \
  --cpu=$CPU \
  --min-instances=$MIN_INSTANCES \
  --max-instances=$MAX_INSTANCES \
  --timeout=300 \
  --concurrency=$CONCURRENCY \
  --set-env-vars=\"ENVIRONMENT=$ENVIRONMENT\" \
  --set-env-vars=\"GOOGLE_CLOUD_PROJECT=$PROJECT_ID\" \
  --project=$PROJECT_ID"

# Add environment-specific environment variables
if [[ "$ENVIRONMENT" == "dev" ]]; then
    DEPLOY_CMD="$DEPLOY_CMD --set-env-vars=\"GCS_BUCKET=${PROJECT_ID}-imgstream-dev\""
elif [[ "$ENVIRONMENT" == "prod" ]]; then
    DEPLOY_CMD="$DEPLOY_CMD --set-env-vars=\"GCS_BUCKET=${PROJECT_ID}-imgstream-prod\""
fi

# Show deployment command
print_status "Deployment command:"
echo "$DEPLOY_CMD"
echo ""

# Dry run mode
if [[ "$DRY_RUN" == "true" ]]; then
    print_warning "Dry run mode - deployment command shown above"
    exit 0
fi

# Confirm deployment
if [[ "$FORCE_DEPLOY" == "false" ]]; then
    read -p "Do you want to proceed with the deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Deployment cancelled by user"
        exit 0
    fi
fi

# Execute deployment
print_status "Deploying to Cloud Run..."
eval "$DEPLOY_CMD" || {
    print_error "Deployment failed"
    exit 1
}

print_success "Deployment completed successfully"

# Get service URL
print_status "Getting service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --format='value(status.url)' \
    --project="$PROJECT_ID")

if [[ -n "$SERVICE_URL" ]]; then
    print_success "Service URL: $SERVICE_URL"
else
    print_warning "Could not retrieve service URL"
fi

# Health check
print_status "Performing health check..."
sleep 10

if [[ "$ENVIRONMENT" == "dev" ]]; then
    # Direct health check for development
    for i in {1..5}; do
        if curl -f -s "${SERVICE_URL}/_stcore/health" > /dev/null; then
            print_success "Health check passed"
            break
        else
            print_warning "Health check failed, retrying in 10s... (attempt $i/5)"
            sleep 10
        fi
        
        if [ $i -eq 5 ]; then
            print_error "Health check failed after 5 attempts"
            print_warning "Service may still be starting up"
        fi
    done
else
    # For production, just check if service responds (IAP will handle auth)
    for i in {1..5}; do
        response=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL" || echo "000")
        if [[ "$response" == "302" ]] || [[ "$response" == "200" ]]; then
            print_success "Health check passed (HTTP $response)"
            break
        else
            print_warning "Health check failed, retrying in 10s... (attempt $i/5) - HTTP $response"
            sleep 10
        fi
        
        if [ $i -eq 5 ]; then
            print_error "Health check failed after 5 attempts"
            print_warning "Service may still be starting up or IAP configuration needed"
        fi
    done
fi

# Show deployment summary
echo ""
echo "=================================="
echo "    Deployment Summary"
echo "=================================="
echo "Service Name:    $SERVICE_NAME"
echo "Environment:     $ENVIRONMENT"
echo "Image:           $IMAGE_TAG"
echo "Service URL:     $SERVICE_URL"
echo "Region:          $REGION"
echo "Status:          Deployed"
echo "=================================="
echo ""

print_success "Deployment completed successfully!"

# Additional information
if [[ "$ENVIRONMENT" == "prod" ]]; then
    echo ""
    echo "Production deployment notes:"
    echo "1. Service is protected by IAP (if configured)"
    echo "2. Configure custom domain and SSL certificate if needed"
    echo "3. Monitor service health and performance"
    echo "4. Check Cloud Run logs for any issues"
fi
