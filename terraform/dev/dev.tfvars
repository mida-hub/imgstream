# Development environment configuration

# Project configuration
project_id = "apps-466614"
region     = "asia-northeast1"

# Storage configuration for development
bucket_location         = "ASIA"
lifecycle_coldline_days = 30  # Standard lifecycle for dev
lifecycle_archive_days  = 365 # Archive after 1 year
lifecycle_delete_days   = 0   # Never auto-delete in development

# Development-specific settings
allowed_domains = [
  # Add your organization's domains here for development
  # "example.com"
]

# allowed_users will be set via environment variable TF_VAR_allowed_users
# Example: export TF_VAR_allowed_users='["your-email@example.com"]'
allowed_users = []

# Cloud Run configuration for development
enable_public_access = true # Enable public access for development
min_instances        = 0    # No minimum instances for cost savings
max_instances        = 3    # Limit scaling for development
cpu_limit            = "1000m"
memory_limit         = "2Gi"

# Container image (will be updated during deployment)
container_image = "asia-northeast1-docker.pkg.dev/apps-466614/imgstream/imgstream:latest"

# Custom domain (optional - configure if you have a domain for dev)
# custom_domain = "imgstream-dev.example.com"

# IAP configuration for development
# iap_support_email will be set via environment variable TF_VAR_iap_support_email
# Example: export TF_VAR_iap_support_email="your-email@example.com"
iap_support_email              = "support@example.com"
enable_iap                     = false # Disable IAP for development (enable public access)
enable_security_policy         = false # Disable security policy for development
enable_waf_rules               = false # Disable WAF rules for development
rate_limit_requests_per_minute = 1000  # Higher rate limit for development
session_duration               = 3600  # 1 hour

# GitHub Actions OIDC configuration is managed in common infrastructure

# Monitoring configuration
# alert_email will be set via environment variable TF_VAR_alert_email
# Example: export TF_VAR_alert_email="alerts@example.com"
alert_email                   = "alerts@example.com"
slack_webhook_url             = ""          # Add Slack webhook URL if needed
storage_alert_threshold_bytes = 85899345920 # 80GB

# Geographic restrictions (optional)
# allowed_countries = ["US", "CA", "JP"]  # Uncomment and specify allowed countries
