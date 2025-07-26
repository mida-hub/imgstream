# Terraform configuration for imgstream photo management app
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
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
