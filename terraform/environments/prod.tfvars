# Production environment configuration

environment = "prod"
region      = "asia-northeast1"

# Storage configuration for production
bucket_location         = "ASIA"
lifecycle_coldline_days = 30   # Standard lifecycle for prod
lifecycle_archive_days  = 365  # Archive after 1 year
lifecycle_delete_days   = 0    # Never auto-delete in production

# Production-specific settings
allowed_domains = [
  # Add your organization's domains here
  # "example.com"
]

allowed_users = [
  # Add specific user emails here
  # "admin@example.com"
]

# Cloud Run configuration for production
enable_public_access = false  # Disable public access (use IAP)
min_instances       = 1      # Keep at least 1 instance running
max_instances       = 10     # Allow scaling up to 10 instances
cpu_limit          = "1000m"
memory_limit       = "2Gi"

# Container image (will be updated during deployment)
container_image = "gcr.io/PROJECT_ID/imgstream:latest"

# Custom domain (optional - configure if you have a domain)
# custom_domain = "imgstream.example.com"

# Secrets are not currently used by the application
# create_default_secrets = false

# IAP configuration for production
iap_support_email = "admin@example.com"  # TODO: Update with actual support email
enable_iap = true  # Enable IAP for production
enable_security_policy = true  # Enable security policy
enable_waf_rules = true  # Enable WAF rules
rate_limit_requests_per_minute = 100  # Standard rate limit
session_duration = 3600  # 1 hour

# Geographic restrictions (optional)
# allowed_countries = ["US", "CA", "JP"]  # Uncomment and specify allowed countries

# GitHub Actions OIDC configuration
github_repository = "your-username/your-repository-name"  # TODO: Replace with actual GitHub repository
