#!/bin/bash
# Docker image build script for imgstream

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROJECT_ID=""
IMAGE_NAME="imgstream"
REPOSITORY_NAME="imgstream"  # Artifact Registry repository name
TAG="latest"
REGISTRY="asia-northeast1-docker.pkg.dev"
PUSH=false
BUILD_ARGS=""
PLATFORM="linux/amd64"
NO_CACHE=false

# Function to display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID [OPTIONS]"
    echo ""
    echo "Required:"
    echo "  -p PROJECT_ID    GCP project ID"
    echo ""
    echo "Optional:"
    echo "  -n IMAGE_NAME    Image name [default: imgstream]"
    echo "  --repo REPO      Repository name [default: imgstream]"
    echo "  -t TAG           Image tag [default: latest]"
    echo "  -r REGISTRY      Container registry [default: asia-northeast1-docker.pkg.dev]"
    echo "  --push           Push image to registry after build"
    echo "  --no-cache       Build without using cache"
    echo "  --build-arg      Build argument (can be used multiple times)"
    echo "  --platform       Target platform [default: linux/amd64]"
    echo "  -h               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project -t v1.0.0 --push"
    echo "  $0 -p my-project --build-arg ENV=prod --push"
    echo "  $0 -p my-project -r asia-northeast1-docker.pkg.dev --push"
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
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --repo)
            REPOSITORY_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --build-arg)
            BUILD_ARGS="$BUILD_ARGS --build-arg $2"
            shift 2
            ;;
        --platform)
            PLATFORM="$2"
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

# Construct full image name based on registry type
if [[ "$REGISTRY" == "gcr.io" ]]; then
    # GCR format: gcr.io/PROJECT_ID/IMAGE_NAME:TAG
    FULL_IMAGE_NAME="${REGISTRY}/${PROJECT_ID}/${IMAGE_NAME}:${TAG}"
else
    # Artifact Registry format: REGISTRY/PROJECT_ID/REPOSITORY/IMAGE_NAME:TAG
    FULL_IMAGE_NAME="${REGISTRY}/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:${TAG}"
fi

# Display configuration
echo "=================================="
echo "    Docker Image Build"
echo "=================================="
echo "Project ID:      $PROJECT_ID"
echo "Repository:      $REPOSITORY_NAME"
echo "Image Name:      $IMAGE_NAME"
echo "Tag:             $TAG"
echo "Registry:        $REGISTRY"
echo "Full Image:      $FULL_IMAGE_NAME"
echo "Platform:        $PLATFORM"
echo "Push:            $PUSH"
echo "No Cache:        $NO_CACHE"
echo "Build Args:      ${BUILD_ARGS:-"None"}"
echo "=================================="
echo ""

# Check if Dockerfile exists
if [[ ! -f "Dockerfile" ]]; then
    print_error "Dockerfile not found in current directory"
    exit 1
fi

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Configure Docker for registry if pushing
if [[ "$PUSH" == "true" ]]; then
    print_status "Configuring Docker for container registry..."

    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it to push to registry."
        exit 1
    fi

    # Configure Docker auth based on registry
    if [[ "$REGISTRY" == "gcr.io" ]]; then
        gcloud auth configure-docker --quiet || {
            print_error "Failed to configure Docker for GCR"
            exit 1
        }
    else
        # Assume Artifact Registry
        gcloud auth configure-docker "${REGISTRY}" --quiet || {
            print_error "Failed to configure Docker for Artifact Registry"
            exit 1
        }
    fi

    # Set project
    gcloud config set project "$PROJECT_ID" || {
        print_error "Failed to set GCP project"
        exit 1
    }
fi

# Build Docker image
print_status "Building Docker image..."

# Construct build command
BUILD_CMD="docker build"

if [[ "$NO_CACHE" == "true" ]]; then
    BUILD_CMD="$BUILD_CMD --no-cache"
fi

BUILD_CMD="$BUILD_CMD --platform $PLATFORM"
BUILD_CMD="$BUILD_CMD $BUILD_ARGS"
BUILD_CMD="$BUILD_CMD -t $FULL_IMAGE_NAME"
BUILD_CMD="$BUILD_CMD ."

print_status "Build command: $BUILD_CMD"
echo ""

# Execute build
eval "$BUILD_CMD" || {
    print_error "Docker build failed"
    exit 1
}

print_success "Docker image built successfully: $FULL_IMAGE_NAME"

# Get image size
IMAGE_SIZE=$(docker images --format "table {{.Size}}" "$FULL_IMAGE_NAME" | tail -n 1)
print_status "Image size: $IMAGE_SIZE"

# Run basic image tests
print_status "Running basic image tests..."

# Test 1: Check if image can start
print_status "Testing if image can start..."
if docker run --rm --entrypoint="" "$FULL_IMAGE_NAME" python --version >/dev/null 2>&1; then
    print_success "✓ Image can start and Python is available"
else
    print_error "✗ Image failed to start or Python not available"
    exit 1
fi

# Test 2: Check if application can import
print_status "Testing if application can import..."
if docker run --rm --entrypoint="" "$FULL_IMAGE_NAME" python -c "import src.imgstream; print('Import successful')" >/dev/null 2>&1; then
    print_success "✓ Application imports successfully"
else
    print_error "✗ Application import failed"
    exit 1
fi

# Test 3: Check if required packages are installed
print_status "Testing if required packages are installed..."
if docker run --rm --entrypoint="" "$FULL_IMAGE_NAME" python -c "import streamlit, google.cloud.storage, duckdb, PIL; print('All packages available')" >/dev/null 2>&1; then
    print_success "✓ All required packages are available"
else
    print_error "✗ Some required packages are missing"
    exit 1
fi

# Push image if requested
if [[ "$PUSH" == "true" ]]; then
    print_status "Pushing image to registry..."

    docker push "$FULL_IMAGE_NAME" || {
        print_error "Failed to push image to registry"
        exit 1
    }

    print_success "Image pushed successfully to registry"

    # Get image digest
    IMAGE_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "$FULL_IMAGE_NAME" 2>/dev/null || echo "N/A")
    if [[ "$IMAGE_DIGEST" != "N/A" ]]; then
        print_status "Image digest: $IMAGE_DIGEST"
    fi
fi

# Show build summary
echo ""
echo "=================================="
echo "    Build Summary"
echo "=================================="
echo "Image:           $FULL_IMAGE_NAME"
echo "Size:            $IMAGE_SIZE"
echo "Platform:        $PLATFORM"
echo "Pushed:          $PUSH"
echo "Status:          Success"
echo "=================================="
echo ""

print_success "Build completed successfully!"
