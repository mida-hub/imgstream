# Development environment configuration

environment = "dev"
region      = "us-central1"

# Storage configuration for development
bucket_location         = "US"
lifecycle_coldline_days = 7   # Shorter lifecycle for dev
lifecycle_archive_days  = 30  # Shorter lifecycle for dev
lifecycle_delete_days   = 90  # Auto-delete after 90 days in dev

# Development-specific settings
allowed_domains = []
allowed_users   = []
