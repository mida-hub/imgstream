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
    prefix = "imgstream/local"
  }
}

provider "google" {
  project = "apps-466614"
  region  = "asia-northeast1"
}

data "google_project" "current" {}
