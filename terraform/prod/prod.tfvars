# Production environment configuration

# Project configuration
project_id = "apps-466614"
region     = "asia-northeast1"

# Storage configuration for production
bucket_location         = "ASIA"
lifecycle_coldline_days = 30  # Standard lifecycle for prod
lifecycle_archive_days  = 365 # Archive after 1 year
lifecycle_delete_days   = 0   # Never auto-delete in production

# Production-specific settings
allowed_domains = [
  # Add your organization's domains here
  # "example.com"
]

# allowed_users will be set via environment variable TF_VAR_allowed_users
# Example: export TF_VAR_allowed_users='["user1@example.com","user2@example.com"]'
# IMPORTANT: Set this environment variable to allow specific users access
allowed_users = []

# Cloud Run configuration for production
enable_public_access = false # Disable public access (use IAP)
min_instances        = 1     # Keep at least 1 instance running
max_instances        = 10    # Allow scaling up to 10 instances
cpu_limit            = "1000m"
memory_limit         = "2Gi"

# Container image configuration
# Note: container_image is deprecated - using shared Artifact Registry with tag management
# The image will be automatically constructed from common Artifact Registry
# Default tag for prod environment is "stable" (can be overridden with container_image_tag)
container_image = "gcr.io/cloudrun/hello" # Fallback only, not used with new system

# Container image tag (optional override for default "stable" tag in prod)
# container_image_tag = "v1.2.3"  # Uncomment to use specific release tag

# Storage security configuration
# enable_public_photo_access = false  # Default: secure (no public access to photos)
# Photos are served via signed URLs through the application for better security

# Custom domain (optional - configure if you have a domain)
# custom_domain = "imgstream.example.com"

# IAP configuration for production
# iap_support_email will be set via environment variable TF_VAR_iap_support_email
# Example: export TF_VAR_iap_support_email="your-email@example.com"
iap_support_email              = "support@example.com"
enable_iap                     = true                # Enable IAP for production
enable_security_policy         = true                # Enable security policy
enable_waf_rules               = true                # Enable WAF rules
rate_limit_requests_per_minute = 100                 # Standard rate limit
session_duration               = 3600                # 1 hour

# GitHub Actions OIDC configuration is managed in common infrastructure

# Monitoring configuration
# alert_email will be set via environment variable TF_VAR_alert_email
# Example: export TF_VAR_alert_email="alerts@example.com"
alert_email                   = "alerts@example.com"
slack_webhook_url             = ""  # Add Slack webhook URL if needed
storage_alert_threshold_bytes = 85899345920  # 80GB

# Geographic restrictions (optional)
# allowed_countries = ["US", "CA", "JP"]  # Uncomment and specify allowed countries
