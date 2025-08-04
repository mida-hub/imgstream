terraform {
  required_version = ">= 1.12"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  backend "gcs" {
    bucket = "tfstate-apps-466614"
    prefix = "imgstream/common"
  }
}

provider "google" {
  project = "apps-466614"
  region  = "asia-northeast1"
}
