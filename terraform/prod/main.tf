# Production environment configuration for ImgStream

terraform {
  required_version = ">= 1.12"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "=6.46.0"
    }
  }
  
  backend "gcs" {
    bucket = "tfstate-apps-466614"
    prefix = "imgstream/prod"
  }
}

provider "google" {
  project = "apps-466614"
  region  = "asia-northeast1"
}

# Data source to read common state (GitHub OIDC resources)
data "terraform_remote_state" "common" {
  backend = "gcs"
  config = {
    bucket = "tfstate-apps-466614"
    prefix = "imgstream/common"
  }
}

# ImgStream application module
module "imgstream" {
  source = "../modules/imgstream"
  
  # Basic configuration
  project_id  = var.project_id
  region      = var.region
  environment = "prod"
  app_name    = var.app_name
  
  # Storage configuration
  bucket_location         = var.bucket_location
  lifecycle_coldline_days = var.lifecycle_coldline_days
  lifecycle_archive_days  = var.lifecycle_archive_days
  lifecycle_delete_days   = var.lifecycle_delete_days
  
  # Access control
  allowed_domains = var.allowed_domains
  allowed_users   = var.allowed_users
  
  # Cloud Run configuration
  container_image      = var.container_image
  container_image_tag  = var.container_image_tag
  enable_public_access = var.enable_public_access
  
  # Storage security configuration
  enable_public_photo_access = false  # Secure: no public access to photos
  custom_domain        = var.custom_domain
  min_instances        = var.min_instances
  max_instances        = var.max_instances
  cpu_limit            = var.cpu_limit
  memory_limit         = var.memory_limit
  
  # IAP configuration
  iap_support_email              = var.iap_support_email
  enable_iap                     = var.enable_iap
  enable_security_policy         = var.enable_security_policy
  enable_waf_rules               = var.enable_waf_rules
  rate_limit_requests_per_minute = var.rate_limit_requests_per_minute
  allowed_countries              = var.allowed_countries
  session_duration               = var.session_duration
  
  # Monitoring configuration
  alert_email                    = var.alert_email
  slack_webhook_url              = var.slack_webhook_url
  storage_alert_threshold_bytes  = var.storage_alert_threshold_bytes
}
