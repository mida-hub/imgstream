# Production environment configuration

# Project configuration
project_id = "apps-466614"
region     = "asia-northeast1"

# Storage configuration for production
bucket_location         = "ASIA"
lifecycle_coldline_days = 30  # Standard lifecycle for prod
lifecycle_archive_days  = 365 # Archive after 1 year
lifecycle_delete_days   = 0   # Never auto-delete in production

# Cloud Run configuration for production
min_instances = 1  # Keep at least 1 instance running
max_instances = 10 # Allow scaling up to 10 instances
cpu_limit     = "1000m"
memory_limit  = "2Gi"

# Container image configuration
# Note: container_image is deprecated - using shared Artifact Registry with tag management
# The image will be automatically constructed from common Artifact Registry
# Default tag for prod environment is "stable" (can be overridden with container_image_tag)
container_image = "gcr.io/cloudrun/hello" # Fallback only, not used with new system

# Container image tag (optional override for default "stable" tag in prod)
container_image_tag = "latest" # Uncomment to use specific release tag

# Custom domain (optional - configure if you have a domain)
# custom_domain = "imgstream.example.com"

# IAP configuration for production
enable_iap = true # Enable IAP for production

# Monitoring configuration
# alert_email will be set via environment variable TF_VAR_alert_email
slack_webhook_url             = ""          # Add Slack webhook URL if needed
storage_alert_threshold_bytes = 85899345920 # 80GB
