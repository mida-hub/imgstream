# Backend configuration for production environment
# This file should be used with: terraform init -backend-config=backend-prod.tf

terraform {
  backend "gcs" {
    bucket = "tfstate-apps-466614"
    prefix = "imgstream/prod"
  }
}
