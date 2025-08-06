#!/bin/bash

# Deploy to Cloud Run dev environment
# This script updates the imgstream-dev service with the latest image

set -e

PROJECT_ID="apps-466614"
REGION="asia-northeast1"
SERVICE_NAME="imgstream-dev"
IMAGE_URL="asia-northeast1-docker.pkg.dev/${PROJECT_ID}/imgstream/imgstream:latest"

echo "Deploying to Cloud Run..."
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Image: ${IMAGE_URL}"

gcloud run services update ${SERVICE_NAME} \
  --region=${REGION} \
  --image=${IMAGE_URL} \
  --project=${PROJECT_ID}

echo "Deployment completed successfully!"
echo "Service URL:"
gcloud run services describe ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID} --format="value(status.url)"
