#!/bin/bash
# Production deployment script for imgstream

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROJECT_ID=""
IMAGE_TAG=""
REGION="us-central1"
FORCE_DEPLOY=false
DRY_RUN=false
SKIP_TERRAFORM=false
SKIP_HEALTH_CHECK=false

# Function to display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID -i IMAGE_TAG [OPTIONS]"
    echo ""
    echo "Required:"
    echo "  -p PROJECT_ID    GCP project ID"
    echo "  -i IMAGE_TAG     Docker image tag to deploy"
    echo ""
    echo "Optional:"
    echo "  -r REGION        GCP region [default: us-central1]"
    echo "  -f               Force deployment without confirmation"
    echo "  --dry-run        Show deployment commands without executing"
    echo "  --skip-terraform Skip Terraform infrastructure deployment"
    echo "  --skip-health    Skip health check after deployment"
    echo "  -h               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project -i gcr.io/my-project/imgstream:v1.0.0"
    echo "  $0 -p my-project -i gcr.io/my-project/imgstream:latest -f"
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
        -i|--image)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
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
        --skip-terraform)
            SKIP_TERRAFORM=true
            shift
            ;;
        --skip-health)
            SKIP_HEALTH_CHECK=true
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

if [[ -z "$IMAGE_TAG" ]]; then
    print_error "IMAGE_TAG is required"
    usage
fi

# Display configuration
echo "=========================================="
echo "    Production Deployment - imgstream"
echo "=========================================="
echo "Project ID:         $PROJECT_ID"
echo "Image Tag:          $IMAGE_TAG"
echo "Region:             $REGION"
echo "Force Deploy:       $FORCE_DEPLOY"
echo "Dry Run:            $DRY_RUN"
echo "Skip Terraform:     $SKIP_TERRAFORM"
echo "Skip Health Check:  $SKIP_HEALTH_CHECK"
echo "=========================================="
echo ""

# Confirm production deployment
if [[ "$FORCE_DEPLOY" == "false" && "$DRY_RUN" == "false" ]]; then
    print_warning "This will deploy to PRODUCTION environment!"
    read -p "Are you sure you want to proceed? (yes/no): " -r
    if [[ ! $REPLY =~ ^(yes|YES)$ ]]; then
        print_warning "Production deployment cancelled by user"
        exit 0
    fi
fi

# Set the project
print_status "Setting GCP project to $PROJECT_ID..."
if [[ "$DRY_RUN" == "false" ]]; then
    gcloud config set project "$PROJECT_ID" || {
        print_error "Failed to set project. Please check if project exists and you have access."
        exit 1
    }
fi

# Check if image exists
print_status "Checking if Docker image exists..."
if [[ "$DRY_RUN" == "false" ]]; then
    if ! gcloud container images describe "$IMAGE_TAG" >/dev/null 2>&1; then
        print_error "Docker image not found: $IMAGE_TAG"
        print_error "Please build and push the image first"
        exit 1
    fi
    print_success "Docker image found: $IMAGE_TAG"
fi

# Deploy infrastructure with Terraform
if [[ "$SKIP_TERRAFORM" == "false" ]]; then
    print_status "Deploying infrastructure with Terraform..."
    
    TERRAFORM_DIR="$(dirname "$(dirname "${BASH_SOURCE[0]}")")/terraform"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "Would run: cd $TERRAFORM_DIR && terraform plan -var-file=environments/prod.tfvars -var=project_id=$PROJECT_ID -var=container_image=$IMAGE_TAG"
    else
        cd "$TERRAFORM_DIR"
        
        # Initialize Terraform
        terraform init
        
        # Plan the deployment
        print_status "Running Terraform plan..."
        terraform plan \
            -var-file="environments/prod.tfvars" \
            -var="project_id=$PROJECT_ID" \
            -var="container_image=$IMAGE_TAG"
        
        # Apply if not dry run
        if [[ "$FORCE_DEPLOY" == "true" ]]; then
            terraform apply \
                -var-file="environments/prod.tfvars" \
                -var="project_id=$PROJECT_ID" \
                -var="container_image=$IMAGE_TAG" \
                -auto-approve
        else
            terraform apply \
                -var-file="environments/prod.tfvars" \
                -var="project_id=$PROJECT_ID" \
                -var="container_image=$IMAGE_TAG"
        fi
        
        print_success "Infrastructure deployment completed"
        cd - > /dev/null
    fi
else
    print_warning "Skipping Terraform infrastructure deployment"
fi

# Deploy application to Cloud Run
print_status "Deploying application to Cloud Run..."

SERVICE_NAME="imgstream-prod"
DEPLOY_CMD="gcloud run deploy $SERVICE_NAME \
  --image=$IMAGE_TAG \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --memory=2Gi \
  --cpu=1 \
  --min-instances=1 \
  --max-instances=10 \
  --timeout=300 \
  --concurrency=80 \
  --set-env-vars=\"ENVIRONMENT=prod\" \
  --set-env-vars=\"GOOGLE_CLOUD_PROJECT=$PROJECT_ID\" \
  --set-env-vars=\"GCS_BUCKET=${PROJECT_ID}-imgstream-prod\" \
  --project=$PROJECT_ID"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "Would run: $DEPLOY_CMD"
else
    eval "$DEPLOY_CMD" || {
        print_error "Cloud Run deployment failed"
        exit 1
    }
    print_success "Cloud Run deployment completed"
fi

# Get service URL
if [[ "$DRY_RUN" == "false" ]]; then
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
fi

# Health check
if [[ "$SKIP_HEALTH_CHECK" == "false" && "$DRY_RUN" == "false" ]]; then
    print_status "Performing health check..."
    sleep 15
    
    # For production, check if service responds (IAP will handle auth)
    for i in {1..10}; do
        response=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL" || echo "000")
        if [[ "$response" == "302" ]] || [[ "$response" == "200" ]]; then
            print_success "Health check passed (HTTP $response)"
            break
        else
            print_warning "Health check failed, retrying in 15s... (attempt $i/10) - HTTP $response"
            sleep 15
        fi
        
        if [ $i -eq 10 ]; then
            print_error "Health check failed after 10 attempts"
            print_warning "Service may still be starting up or IAP configuration needed"
        fi
    done
else
    print_warning "Skipping health check"
fi

# Show deployment summary
echo ""
echo "=========================================="
echo "    Production Deployment Summary"
echo "=========================================="
echo "Service Name:       $SERVICE_NAME"
echo "Environment:        prod"
echo "Image:              $IMAGE_TAG"
if [[ "$DRY_RUN" == "false" ]]; then
    echo "Service URL:        $SERVICE_URL"
fi
echo "Region:             $REGION"
echo "Status:             $([ "$DRY_RUN" == "true" ] && echo "Dry Run" || echo "Deployed")"
echo "=========================================="
echo ""

if [[ "$DRY_RUN" == "false" ]]; then
    print_success "Production deployment completed successfully!"
    
    echo ""
    echo "Post-deployment checklist:"
    echo "1. ✓ Infrastructure deployed with Terraform"
    echo "2. ✓ Application deployed to Cloud Run"
    echo "3. ✓ Health check performed"
    echo "4. □ Configure custom domain (if needed)"
    echo "5. □ Set up monitoring and alerting"
    echo "6. □ Verify IAP configuration"
    echo "7. □ Test application functionality"
    echo "8. □ Update DNS records (if using custom domain)"
    echo ""
    echo "Important notes:"
    echo "- Service is protected by IAP authentication"
    echo "- Monitor Cloud Run logs for any issues"
    echo "- Check Cloud Monitoring for performance metrics"
    echo "- Ensure all secrets are properly configured"
else
    print_success "Dry run completed - no changes were made"
fi
