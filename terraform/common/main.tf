# Common infrastructure for ImgStream project
# This should be applied once before deploying dev/prod environments

terraform {
  required_version = ">= 1.12"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  # Backend configuration for common resources
  backend "gcs" {
    bucket = "apps-466614-terraform-state"
    prefix = "common"
  }
}

# Configure the Google Cloud Provider
provider "google" {
  project = var.project_id
  region  = var.region
}
