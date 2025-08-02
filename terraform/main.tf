# Terraform configuration for imgstream photo management app
terraform {
  required_version = ">= 1.12"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  # Backend configuration for remote state storage
  # Use environment-specific backend config files:
  # - Development: terraform init -backend-config=backend-dev.hcl
  # - Production: terraform init -backend-config=backend-prod.hcl
  backend "gcs" {
    # Configuration will be provided via backend config files
  }
}

# Configure the Google Cloud Provider
provider "google" {
  project = var.project_id
  region  = var.region
}

# Data source for current project
data "google_project" "current" {}

# Data source for current client config
data "google_client_config" "current" {}
