# Artifact Registry configuration for imgstream

# Artifact Registry repository for container images
resource "google_artifact_registry_repository" "imgstream" {
  location      = var.region
  repository_id = "imgstream"
  description   = "Docker repository for ImgStream application"
  format        = "DOCKER"

  labels = {
    environment = var.environment
    app         = var.app_name
    managed-by  = "terraform"
  }
}

# IAM binding for Cloud Run service account to pull images
resource "google_artifact_registry_repository_iam_member" "cloud_run_reader" {
  location   = google_artifact_registry_repository.imgstream.location
  repository = google_artifact_registry_repository.imgstream.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.cloud_run.email}"
}
