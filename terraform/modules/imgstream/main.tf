# Main Terraform configuration for ImgStream module
terraform {
  required_version = ">= 1.12"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
}

# Data source for current project
data "google_project" "current" {}

# Data source for current client config
data "google_client_config" "current" {}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
  ])

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}
