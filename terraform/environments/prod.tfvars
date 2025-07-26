# Production environment configuration

environment = "prod"
region      = "us-central1"

# Storage configuration for production
bucket_location         = "US"
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
