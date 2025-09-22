# Data source for current project
data "google_project" "current" {}

# Data source for current client config
data "google_client_config" "current" {}

# Data source to read common infrastructure state (Artifact Registry, GitHub OIDC)
data "terraform_remote_state" "common" {
  backend = "gcs"
  config = {
    bucket = "tfstate-apps-466614"
    prefix = "imgstream/common"
  }
}

# Local variables for image URL construction
locals {
  # Default tags per environment
  default_image_tags = {
    dev     = "latest"
    staging = "staging"
    prod    = "stable"
  }

  # Determine the image tag to use
  image_tag = var.container_image_tag != null ? var.container_image_tag : local.default_image_tags[var.environment]

  # Construct the full container image URL from common Artifact Registry
  # Format: REGISTRY/PROJECT_ID/REPOSITORY/IMAGE_NAME:TAG
  container_image = "${data.terraform_remote_state.common.outputs.artifact_registry_repository_url}/${var.app_name}:${local.image_tag}"
}

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

# IAM binding for Cloud Run service account to pull images from shared Artifact Registry
resource "google_artifact_registry_repository_iam_member" "cloud_run_reader" {
  location   = data.terraform_remote_state.common.outputs.artifact_registry_location
  repository = data.terraform_remote_state.common.outputs.artifact_registry_repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.cloud_run.email}"
}
