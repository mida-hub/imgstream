# Shared Artifact Registry configuration for ImgStream

# Artifact Registry repository for container images (shared across environments)
resource "google_artifact_registry_repository" "imgstream" {
  location      = var.region
  repository_id = "imgstream"
  description   = "Shared Docker repository for ImgStream application across all environments"
  format        = "DOCKER"

  labels = {
    shared     = "true"
    app        = "imgstream"
    managed-by = "terraform"
  }
}

# IAM binding for GitHub Actions service account to push images
resource "google_artifact_registry_repository_iam_member" "github_actions_writer" {
  location   = google_artifact_registry_repository.imgstream.location
  repository = google_artifact_registry_repository.imgstream.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.github_actions.email}"
}

# IAM binding for GitHub Actions service account to read images (for deployment)
resource "google_artifact_registry_repository_iam_member" "github_actions_reader" {
  location   = google_artifact_registry_repository.imgstream.location
  repository = google_artifact_registry_repository.imgstream.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.github_actions.email}"
}

# IAM binding for Cloud Run service accounts to pull images
# This will be configured per environment via variables
resource "google_artifact_registry_repository_iam_member" "cloud_run_readers" {
  for_each = toset(var.cloud_run_service_accounts)

  location   = google_artifact_registry_repository.imgstream.location
  repository = google_artifact_registry_repository.imgstream.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${each.value}"
}
