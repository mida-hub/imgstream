# GitHub Actions OIDC authentication setup for Google Cloud

# Workload Identity Pool for GitHub Actions
resource "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions OIDC authentication"
  disabled                  = false
}

# Workload Identity Pool Provider for GitHub
resource "google_iam_workload_identity_pool_provider" "github_actions" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC identity pool provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
  
  attribute_condition = "attribute.repository == \"${var.github_repository}\""
}

# Service Account for GitHub Actions
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-sa"
  display_name = "GitHub Actions Service Account"
  description  = "Service account for GitHub Actions deployments"
}

# IAM binding for Workload Identity User
resource "google_service_account_iam_binding" "github_actions_workload_identity" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/${var.github_repository}"
  ]
}

# Project-level IAM roles for the service account
resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset([
    "roles/run.admin",
    "roles/storage.admin",
    "roles/artifactregistry.admin",
    "roles/iam.serviceAccountUser",
    "roles/monitoring.editor",
    "roles/logging.admin",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}
