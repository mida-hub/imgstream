# Backend configuration for development environment
# This file should be used with: terraform init -backend-config=backend-dev.tf

terraform {
  backend "gcs" {
    bucket = "tfstate-apps-466614"
    prefix = "imgstream/dev"
  }
}
