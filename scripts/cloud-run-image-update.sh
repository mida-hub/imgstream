#!/bin/bash

# Cloud Run image update script
# This script updates the Cloud Run service with a new image
# Usage: ./cloud-run-image-update.sh <environment> [image_tag]
# Example: ./cloud-run-image-update.sh dev latest
# Example: ./cloud-run-image-update.sh prod v1.2.3

set -e

# Check arguments
if [ $# -lt 1 ]; then
    echo "❌ Error: Environment argument is required"
    echo "Usage: $0 <environment> [image_tag]"
    echo "  environment: dev or prod"
    echo "  image_tag: optional, defaults to 'latest'"
    echo ""
    echo "Examples:"
    echo "  $0 dev"
    echo "  $0 prod latest"
    echo "  $0 dev v1.2.3"
    exit 1
fi

ENVIRONMENT=$1
IMAGE_TAG=${2:-latest}

# Validate environment
if [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
    echo "❌ Error: Environment must be 'dev' or 'prod'"
    exit 1
fi

# Configuration based on environment
PROJECT_ID="apps-466614"
REGION="asia-northeast1"

if [ "$ENVIRONMENT" = "dev" ]; then
    SERVICE_NAME="imgstream-dev"
elif [ "$ENVIRONMENT" = "prod" ]; then
    SERVICE_NAME="imgstream-prod"
fi

IMAGE_URL="asia-northeast1-docker.pkg.dev/${PROJECT_ID}/imgstream/imgstream:${IMAGE_TAG}"

echo "🚀 Starting Cloud Run image update..."
echo "🏷️  Environment: ${ENVIRONMENT}"
echo "📦 Image tag: ${IMAGE_TAG}"
echo "🌐 Project: ${PROJECT_ID}"
echo "📍 Region: ${REGION}"
echo "🔧 Service: ${SERVICE_NAME}"
echo "🖼️  Image: ${IMAGE_URL}"

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Error: Not authenticated with gcloud. Please run 'gcloud auth login'"
    exit 1
fi

# Set the project
echo "📋 Setting project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

# Verify image exists
echo "🔍 Verifying image exists: ${IMAGE_URL}..."
if ! gcloud artifacts docker images describe ${IMAGE_URL} --quiet >/dev/null 2>&1; then
    echo "❌ Error: Image ${IMAGE_URL} not found."
    echo "💡 Available tags:"
    gcloud artifacts docker images list asia-northeast1-docker.pkg.dev/${PROJECT_ID}/imgstream/imgstream --limit=10 --sort-by=~UPDATE_TIME --format="table(tags,updateTime)"
    exit 1
fi
echo "✅ Image verified: ${IMAGE_URL}"

# Update Cloud Run service
echo "🔄 Updating Cloud Run service..."
gcloud run services update ${SERVICE_NAME} \
    --region=${REGION} \
    --image=${IMAGE_URL} \
    --project=${PROJECT_ID} \
    --quiet

if [ $? -eq 0 ]; then
    echo "✅ Cloud Run service updated successfully!"
    echo "🏷️  Environment: ${ENVIRONMENT}"
    echo "📦 Image: ${IMAGE_URL}"
    echo "🌐 Service URL:"
    gcloud run services describe ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID} --format="value(status.url)"
else
    echo "❌ Error: Failed to update Cloud Run service"
    exit 1
fi

echo "🎉 Image update completed for ${ENVIRONMENT} environment!"
