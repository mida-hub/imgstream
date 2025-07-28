#!/bin/bash
# Setup production secrets and environment variables for imgstream

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROJECT_ID=""
REGION="us-central1"
DRY_RUN=false
FORCE_UPDATE=false

# Function to display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID [OPTIONS]"
    echo ""
    echo "Required:"
    echo "  -p PROJECT_ID    GCP project ID"
    echo ""
    echo "Optional:"
    echo "  -r REGION        GCP region [default: us-central1]"
    echo "  -f               Force update existing secrets"
    echo "  --dry-run        Show what would be created without executing"
    echo "  -h               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project"
    echo "  $0 -p my-project -f --dry-run"
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
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_UPDATE=true
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

# Display configuration
echo "=========================================="
echo "    Production Secrets Setup"
echo "=========================================="
echo "Project ID:      $PROJECT_ID"
echo "Region:          $REGION"
echo "Force Update:    $FORCE_UPDATE"
echo "Dry Run:         $DRY_RUN"
echo "=========================================="
echo ""

# Set the project
print_status "Setting GCP project to $PROJECT_ID..."
if [[ "$DRY_RUN" == "false" ]]; then
    gcloud config set project "$PROJECT_ID" || {
        print_error "Failed to set project. Please check if project exists and you have access."
        exit 1
    }
fi

# Enable required APIs
print_status "Enabling required APIs..."
REQUIRED_APIS=(
    "secretmanager.googleapis.com"
    "run.googleapis.com"
    "storage.googleapis.com"
    "cloudbuild.googleapis.com"
    "containerregistry.googleapis.com"
    "iap.googleapis.com"
)

for api in "${REQUIRED_APIS[@]}"; do
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "Would enable API: $api"
    else
        if gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
            print_success "✓ $api is already enabled"
        else
            print_status "Enabling $api..."
            gcloud services enable "$api"
            print_success "✓ $api enabled"
        fi
    fi
done

# Function to create or update secret
create_or_update_secret() {
    local secret_name="$1"
    local secret_value="$2"
    local description="$3"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "Would create/update secret: $secret_name"
        return
    fi
    
    # Check if secret exists
    if gcloud secrets describe "$secret_name" >/dev/null 2>&1; then
        if [[ "$FORCE_UPDATE" == "true" ]]; then
            print_status "Updating existing secret: $secret_name"
            echo -n "$secret_value" | gcloud secrets versions add "$secret_name" --data-file=-
            print_success "✓ Secret $secret_name updated"
        else
            print_warning "Secret $secret_name already exists (use -f to force update)"
        fi
    else
        print_status "Creating secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create "$secret_name" \
            --data-file=- \
            --labels="environment=prod,app=imgstream" \
            --replication-policy="automatic"
        
        # Add description if provided
        if [[ -n "$description" ]]; then
            gcloud secrets update "$secret_name" --update-labels="description=$description"
        fi
        
        print_success "✓ Secret $secret_name created"
    fi
}

# Function to prompt for secret value
prompt_for_secret() {
    local secret_name="$1"
    local prompt_text="$2"
    local is_sensitive="${3:-true}"
    
    echo ""
    echo "Setting up secret: $secret_name"
    echo "$prompt_text"
    
    if [[ "$is_sensitive" == "true" ]]; then
        read -s -p "Enter value (input hidden): " secret_value
        echo ""
    else
        read -p "Enter value: " secret_value
    fi
    
    if [[ -z "$secret_value" ]]; then
        print_warning "Empty value provided for $secret_name, skipping..."
        return 1
    fi
    
    echo "$secret_value"
}

# Create application secrets
print_status "Setting up application secrets..."

# Database encryption key
if secret_value=$(prompt_for_secret "db-encryption-key" "Database encryption key (32 characters recommended):"); then
    create_or_update_secret "db-encryption-key" "$secret_value" "Database encryption key for imgstream"
fi

# Session secret key
if secret_value=$(prompt_for_secret "session-secret-key" "Session secret key (64 characters recommended):"); then
    create_or_update_secret "session-secret-key" "$secret_value" "Session secret key for imgstream"
fi

# JWT secret (if using custom JWT)
if secret_value=$(prompt_for_secret "jwt-secret" "JWT secret key (optional, press Enter to skip):"); then
    create_or_update_secret "jwt-secret" "$secret_value" "JWT secret key for imgstream"
fi

# API keys (if needed)
echo ""
read -p "Do you need to set up external API keys? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if secret_value=$(prompt_for_secret "external-api-key" "External API key:"); then
        create_or_update_secret "external-api-key" "$secret_value" "External API key for imgstream"
    fi
fi

# OAuth client secrets (if using custom OAuth)
echo ""
read -p "Do you need to set up OAuth client secrets? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if secret_value=$(prompt_for_secret "oauth-client-secret" "OAuth client secret:"); then
        create_or_update_secret "oauth-client-secret" "$secret_value" "OAuth client secret for imgstream"
    fi
fi

# Set up IAM permissions for Cloud Run to access secrets
print_status "Setting up IAM permissions for Cloud Run service account..."

# Get the default compute service account
COMPUTE_SA="${PROJECT_ID}-compute@developer.gserviceaccount.com"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "Would grant Secret Manager access to: $COMPUTE_SA"
else
    # Grant Secret Manager Secret Accessor role
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$COMPUTE_SA" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet
    
    print_success "✓ Granted Secret Manager access to Cloud Run service account"
fi

# Create production GCS bucket if it doesn't exist
BUCKET_NAME="${PROJECT_ID}-imgstream-prod"
print_status "Setting up production GCS bucket: $BUCKET_NAME"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "Would create/configure bucket: $BUCKET_NAME"
else
    if gsutil ls -b "gs://$BUCKET_NAME" >/dev/null 2>&1; then
        print_success "✓ Bucket $BUCKET_NAME already exists"
    else
        print_status "Creating bucket: $BUCKET_NAME"
        gsutil mb -p "$PROJECT_ID" -c STANDARD -l US "gs://$BUCKET_NAME"
        
        # Set up lifecycle policy
        cat > /tmp/lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 30}
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "ARCHIVE"},
        "condition": {"age": 365}
      }
    ]
  }
}
EOF
        
        gsutil lifecycle set /tmp/lifecycle.json "gs://$BUCKET_NAME"
        rm /tmp/lifecycle.json
        
        print_success "✓ Bucket $BUCKET_NAME created with lifecycle policy"
    fi
    
    # Set up CORS policy for the bucket
    cat > /tmp/cors.json << EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "PUT", "POST", "DELETE"],
    "responseHeader": ["Content-Type", "Access-Control-Allow-Origin"],
    "maxAgeSeconds": 3600
  }
]
EOF
    
    gsutil cors set /tmp/cors.json "gs://$BUCKET_NAME"
    rm /tmp/cors.json
    
    print_success "✓ CORS policy configured for bucket"
fi

# Show summary
echo ""
echo "=========================================="
echo "    Production Setup Summary"
echo "=========================================="
echo "Project ID:          $PROJECT_ID"
echo "Region:              $REGION"
echo "Bucket:              $BUCKET_NAME"
echo "Service Account:     $COMPUTE_SA"
echo "Status:              $([ "$DRY_RUN" == "true" ] && echo "Dry Run" || echo "Configured")"
echo "=========================================="
echo ""

if [[ "$DRY_RUN" == "false" ]]; then
    print_success "Production secrets and resources setup completed!"
    
    echo ""
    echo "Next steps:"
    echo "1. ✓ Secrets created in Secret Manager"
    echo "2. ✓ IAM permissions configured"
    echo "3. ✓ GCS bucket created and configured"
    echo "4. □ Update terraform/environments/prod.tfvars with your specific values"
    echo "5. □ Configure IAP OAuth consent screen"
    echo "6. □ Set up custom domain (if needed)"
    echo "7. □ Deploy infrastructure with Terraform"
    echo "8. □ Deploy application to Cloud Run"
    echo ""
    echo "Important notes:"
    echo "- Keep your secret values secure and don't commit them to version control"
    echo "- Regularly rotate secrets for security"
    echo "- Monitor Secret Manager usage and access logs"
    echo "- Test the application after deployment"
else
    print_success "Dry run completed - no changes were made"
fi
