#!/bin/bash

# Cloud Run deployment script for imgstream
set -e

# Default values
PROJECT_ID=""
ENVIRONMENT="dev"
REGION="us-central1"
IMAGE_TAG="latest"

# Function to display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID [-e ENVIRONMENT] [-r REGION] [-t IMAGE_TAG]"
    echo ""
    echo "Options:"
    echo "  -p PROJECT_ID    GCP project ID (required)"
    echo "  -e ENVIRONMENT   Environment (dev|prod) [default: dev]"
    echo "  -r REGION        GCP region [default: us-central1]"
    echo "  -t IMAGE_TAG     Container image tag [default: latest]"
    echo "  -h               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project-id -e dev"
    echo "  $0 -p my-project-id -e prod -t v1.0.0"
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
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
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

echo "=== Cloud Run Deployment ==="
echo "Project ID: $PROJECT_ID"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Image Tag: $IMAGE_TAG"
echo ""

# Set the project
gcloud config set project "$PROJECT_ID"

# Build and push container image
echo "Building container image..."
IMAGE_NAME="gcr.io/$PROJECT_ID/imgstream:$IMAGE_TAG"

docker build -f Dockerfile.cloudrun -t "$IMAGE_NAME" .
docker push "$IMAGE_NAME"

echo "Container image pushed: $IMAGE_NAME"

# Set environment-specific variables
if [[ "$ENVIRONMENT" == "prod" ]]; then
    MEMORY_LIMIT="2Gi"
    CPU_LIMIT="1000m"
    MAX_INSTANCES="10"
    MIN_INSTANCES="1"
    ALLOW_UNAUTHENTICATED="--no-allow-unauthenticated"
else
    MEMORY_LIMIT="1Gi"
    CPU_LIMIT="1000m"
    MAX_INSTANCES="3"
    MIN_INSTANCES="0"
    ALLOW_UNAUTHENTICATED="--allow-unauthenticated"
fi

SERVICE_NAME="imgstream-$ENVIRONMENT"
SERVICE_ACCOUNT="imgstream-cloud-run-$ENVIRONMENT@$PROJECT_ID.iam.gserviceaccount.com"

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME" \
    --region "$REGION" \
    --platform managed \
    --service-account "$SERVICE_ACCOUNT" \
    $ALLOW_UNAUTHENTICATED \
    --memory "$MEMORY_LIMIT" \
    --cpu "$CPU_LIMIT" \
    --concurrency 80 \
    --timeout 300 \
    --max-instances "$MAX_INSTANCES" \
    --min-instances "$MIN_INSTANCES" \
    --set-env-vars "ENVIRONMENT=$ENVIRONMENT,GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION" \
    --quiet

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)")

echo ""
echo "=== Deployment Complete ==="
echo "Service Name: $SERVICE_NAME"
echo "Service URL: $SERVICE_URL"
echo "Region: $REGION"
echo ""

if [[ "$ENVIRONMENT" == "dev" ]]; then
    echo "Development deployment allows public access."
    echo "You can access the application at: $SERVICE_URL"
else
    echo "Production deployment requires authentication."
    echo "Configure Cloud IAP to access the application."
fi
