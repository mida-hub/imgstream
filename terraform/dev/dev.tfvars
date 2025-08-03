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

allowed_users = ["rusuden0106@gmail.com"]

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
iap_support_email              = "rusuden0106@gmail.com"
enable_iap                     = false               # Disable IAP for development (enable public access)
enable_security_policy         = false               # Disable security policy for development
enable_waf_rules               = false               # Disable WAF rules for development
rate_limit_requests_per_minute = 1000                # Higher rate limit for development
session_duration               = 3600                # 1 hour

# GitHub Actions OIDC configuration is managed in common infrastructure

# Monitoring configuration
alert_email                   = "rusuden0106@gmail.com"
slack_webhook_url             = ""  # Add Slack webhook URL if needed
storage_alert_threshold_bytes = 85899345920  # 80GB

# Geographic restrictions (optional)
# allowed_countries = ["US", "CA", "JP"]  # Uncomment and specify allowed countries
