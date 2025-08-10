# Development environment configuration

# Project configuration
project_id = "apps-466614"
region     = "asia-northeast1"

# Storage configuration for development
bucket_location         = "ASIA"
lifecycle_coldline_days = 30  # Standard lifecycle for dev
lifecycle_archive_days  = 365 # Archive after 1 year
lifecycle_delete_days   = 0   # Never auto-delete in development

# Cloud Run configuration for development
min_instances = 0 # No minimum instances for cost savings
max_instances = 1 # Limit scaling for development
cpu_limit     = "1000m"
memory_limit  = "2Gi"

# Container image configuration
# Note: container_image is deprecated - using shared Artifact Registry with tag management
# The image will be automatically constructed from common Artifact Registry
# Default tag for dev environment is "latest" (can be overridden with container_image_tag)
container_image = "gcr.io/cloudrun/hello" # Fallback only, not used with new system

# Container image tag (optional override for default "latest" tag in dev)
# container_image_tag = "dev-v1.2.3"  # Uncomment to use specific tag

# Custom domain (optional - configure if you have a domain for dev)
# custom_domain = "imgstream-dev.example.com"

# IAP configuration for development
enable_iap = false # Disable IAP (requires organization)

# Monitoring configuration
slack_webhook_url             = ""          # Add Slack webhook URL if needed
storage_alert_threshold_bytes = 85899345920 # 80GB
