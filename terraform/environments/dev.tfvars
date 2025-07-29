# Development environment configuration

environment = "dev"
region      = "asia-northeast1"

# Storage configuration for development
bucket_location         = "ASIA"
lifecycle_coldline_days = 7   # Shorter lifecycle for dev
lifecycle_archive_days  = 30  # Shorter lifecycle for dev
lifecycle_delete_days   = 90  # Auto-delete after 90 days in dev

# Development-specific settings
allowed_domains = []
allowed_users   = []

# Cloud Run configuration for development
enable_public_access = true  # Allow public access for development
min_instances       = 0     # Scale to zero when not in use
max_instances       = 3     # Limit max instances for cost control
cpu_limit          = "1000m"
memory_limit       = "1Gi"

# Container image (update with actual image)
container_image = "gcr.io/cloudrun/hello"  # Placeholder

# Create default secrets
create_default_secrets = true

# IAP configuration for development
iap_support_email = "developer@example.com"  # Update with actual email
enable_iap = false  # Disable IAP for development (use public access)
enable_security_policy = false  # Disable security policy for development
enable_waf_rules = false
rate_limit_requests_per_minute = 1000  # Higher limit for development
session_duration = 7200  # 2 hours
