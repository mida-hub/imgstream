# GCS buckets and lifecycle policies for imgstream

# Random suffix for bucket names to ensure uniqueness
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# Photos storage bucket
resource "google_storage_bucket" "photos" {
  name     = "${var.app_name}-photos-${var.environment}-${random_id.bucket_suffix.hex}"
  location = var.bucket_location

  # Enable uniform bucket-level access
  uniform_bucket_level_access = true

  # Versioning configuration
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

  # Lifecycle management
  lifecycle_rule {
    condition {
      age = var.lifecycle_coldline_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = var.lifecycle_archive_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  # Optional: Delete old objects (disabled by default)
  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_delete_days > 0 ? [1] : []
    content {
      condition {
        age = var.lifecycle_delete_days
      }
      action {
        type = "Delete"
      }
    }
  }

  # Labels for resource management
  labels = {
    environment = var.environment
    app         = var.app_name
    purpose     = "photos"
  }
}

# Database backup bucket
resource "google_storage_bucket" "database" {
  name     = "${var.app_name}-database-${var.environment}-${random_id.bucket_suffix.hex}"
  location = var.bucket_location

  # Enable uniform bucket-level access
  uniform_bucket_level_access = true

  # Versioning for database backups - keep only 3 generations
  versioning {
    enabled = true
  }

  # Lifecycle management for versioning - keep only 3 versions
  lifecycle_rule {
    condition {
      num_newer_versions = 3
    }
    action {
      type = "Delete"
    }
  }

  # Move non-current versions to COLDLINE after 7 days
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 7
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  # Move non-current versions to ARCHIVE after 90 days
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  # Labels for resource management
  labels = {
    environment = var.environment
    app         = var.app_name
    purpose     = "database"
  }
}

# Service account for Cloud Run
resource "google_service_account" "cloud_run" {
  account_id   = "${var.app_name}-cloud-run-${var.environment}"
  display_name = "Cloud Run service account for ${var.app_name}"
  description  = "Service account used by Cloud Run for ${var.app_name} application"
}

# IAM binding for photos bucket - Cloud Run service account
resource "google_storage_bucket_iam_member" "photos_cloud_run_admin" {
  bucket = google_storage_bucket.photos.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

# IAM binding for database bucket - Cloud Run service account
resource "google_storage_bucket_iam_member" "database_cloud_run_admin" {
  bucket = google_storage_bucket.database.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Optional public read access for photos bucket
# SECURITY NOTE: This allows public access to all objects in the bucket
# Default is disabled (false) for better security - photos are served via signed URLs
# Only enable if you need direct public access to photos (not recommended)
resource "google_storage_bucket_iam_member" "photos_public_read" {
  count  = var.enable_public_photo_access ? 1 : 0
  bucket = google_storage_bucket.photos.name
  role   = "roles/storage.legacyObjectReader"
  member = "allUsers"
}
