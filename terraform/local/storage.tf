# GCS buckets and lifecycle policies for imgstream

# Photos storage bucket
resource "google_storage_bucket" "local" {
  name     = "${local.app_name}-${local.environment}-${data.google_project.current.project_id}"
  location = local.bucket_location

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }

  # CORS configuration for web access
  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  labels = {
    environment = local.environment
    app         = local.app_name
    purpose     = "photos-and-database"
  }
}
