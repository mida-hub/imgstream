# Development environment configuration for ImgStream

terraform {
  required_version = ">= 1.12"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.46.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.46.0"
    }
  }

  backend "gcs" {
    bucket = "tfstate-apps-466614"
    prefix = "imgstream/dev"
  }
}

provider "google" {
  project = "apps-466614"
  region  = "asia-northeast1"
}

provider "google-beta" {
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
  environment = "dev"
  app_name    = var.app_name

  # Storage configuration
  bucket_location         = var.bucket_location
  lifecycle_coldline_days = var.lifecycle_coldline_days
  lifecycle_archive_days  = var.lifecycle_archive_days
  lifecycle_delete_days   = var.lifecycle_delete_days

  # Access control
  allowed_users = var.allowed_users

  # Cloud Run configuration
  container_image     = var.container_image
  container_image_tag = var.container_image_tag

  # Storage security configuration
  custom_domain = var.custom_domain
  min_instances = var.min_instances
  max_instances = var.max_instances
  cpu_limit     = var.cpu_limit
  memory_limit  = var.memory_limit

  # IAP configuration
  enable_iap = var.enable_iap

  # Monitoring configuration
  alert_email                   = var.alert_email
  slack_webhook_url             = var.slack_webhook_url
  storage_alert_threshold_bytes = var.storage_alert_threshold_bytes
}
