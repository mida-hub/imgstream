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
# Note: Only includes roles actually needed by ImgStream application
resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset([
    "roles/run.admin",              # Cloud Run administration
    "roles/storage.admin",          # Cloud Storage administration
    "roles/artifactregistry.admin", # Artifact Registry administration
    "roles/iam.serviceAccountUser", # Service account usage
    "roles/monitoring.editor",      # Monitoring resources
    "roles/logging.admin",          # Logging administration
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# Removed roles (not needed by ImgStream):
# - roles/cloudsql.admin: ImgStream uses DuckDB, not Cloud SQL
# - roles/secretmanager.admin: ImgStream uses environment variables, not Secret Manager
# - roles/cloudtrace.agent: Not currently implemented
# - roles/clouddebugger.agent: Not currently implemented

# Output the Workload Identity Provider name for GitHub Actions configuration
output "workload_identity_provider" {
  description = "The full name of the workload identity provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}

# Output the service account email
output "github_actions_service_account_email" {
  description = "Email of the GitHub Actions service account"
  value       = google_service_account.github_actions.email
}
