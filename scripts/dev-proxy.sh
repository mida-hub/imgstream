#!/bin/bash

# Development environment proxy script for ImgStream
# This script creates a secure proxy to the development Cloud Run service

set -e

# Configuration
SERVICE_NAME="imgstream-dev"
REGION="asia-northeast1"
PROJECT_ID="apps-466614"
LOCAL_PORT="8080"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if gcloud is installed and authenticated
check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first:"
        echo "https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    # Check if authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_error "You are not authenticated with gcloud. Please run:"
        echo "gcloud auth login"
        exit 1
    fi

    # Check if project is set
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
    if [[ "$CURRENT_PROJECT" != "$PROJECT_ID" ]]; then
        print_warning "Current project is '$CURRENT_PROJECT', switching to '$PROJECT_ID'"
        gcloud config set project "$PROJECT_ID"
    fi
}

# Function to check if the service exists
check_service() {
    print_info "Checking if Cloud Run service exists..."
    
    if ! gcloud run services describe "$SERVICE_NAME" --region="$REGION" --quiet &>/dev/null; then
        print_error "Cloud Run service '$SERVICE_NAME' not found in region '$REGION'"
        print_info "Make sure the service is deployed by running:"
        echo "cd terraform/dev && terraform apply -var-file=dev.tfvars"
        exit 1
    fi
    
    print_success "Cloud Run service found"
}

# Function to check if port is available
check_port() {
    if lsof -Pi :$LOCAL_PORT -sTCP:LISTEN -t >/dev/null ; then
        print_error "Port $LOCAL_PORT is already in use"
        print_info "Please stop the process using port $LOCAL_PORT or choose a different port"
        exit 1
    fi
}

# Function to start the proxy
start_proxy() {
    print_info "Starting secure proxy to $SERVICE_NAME..."
    print_info "Local URL: http://localhost:$LOCAL_PORT"
    print_info "Press Ctrl+C to stop the proxy"
    echo ""
    
    # Start the proxy
    gcloud run services proxy "$SERVICE_NAME" \
        --region="$REGION" \
        --port="$LOCAL_PORT"
}

# Function to handle cleanup on exit
cleanup() {
    print_info "Stopping proxy..."
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    echo "🚀 ImgStream Development Proxy"
    echo "================================"
    echo ""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--port)
                LOCAL_PORT="$2"
                shift 2
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  -p, --port PORT    Local port to use (default: 8080)"
                echo "  -h, --help         Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                 # Start proxy on port 8080"
                echo "  $0 -p 3000         # Start proxy on port 3000"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Run checks
    check_gcloud
    check_service
    check_port
    
    # Start proxy
    start_proxy
}

# Run main function
main "$@"
