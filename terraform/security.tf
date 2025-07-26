# Security and access control configurations

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "storage.googleapis.com",
    "run.googleapis.com",
    "iap.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com"
  ])

  service = each.value

  disable_dependent_services = false
  disable_on_destroy         = false
}

# Cloud Run service account permissions
resource "google_project_iam_member" "cloud_run_permissions" {
  for_each = toset([
    "roles/storage.objectAdmin",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent"
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Security policy for buckets
resource "google_storage_bucket_iam_binding" "photos_prevent_public_write" {
  bucket = google_storage_bucket.photos.name
  role   = "roles/storage.objectCreator"
  
  members = [
    "serviceAccount:${google_service_account.cloud_run.email}"
  ]
}

resource "google_storage_bucket_iam_binding" "database_prevent_public_access" {
  bucket = google_storage_bucket.database.name
  role   = "roles/storage.objectViewer"
  
  members = [
    "serviceAccount:${google_service_account.cloud_run.email}"
  ]
}

# Bucket-level security settings
resource "google_storage_bucket_iam_binding" "photos_admin_only" {
  bucket = google_storage_bucket.photos.name
  role   = "roles/storage.admin"
  
  members = [
    "serviceAccount:${google_service_account.cloud_run.email}"
  ]
}

resource "google_storage_bucket_iam_binding" "database_admin_only" {
  bucket = google_storage_bucket.database.name
  role   = "roles/storage.admin"
  
  members = [
    "serviceAccount:${google_service_account.cloud_run.email}"
  ]
}

# Organization policy constraints (if applicable)
# These would typically be set at the organization level
# resource "google_organization_policy" "storage_public_access_prevention" {
#   org_id     = var.org_id
#   constraint = "constraints/storage.publicAccessPrevention"
#   
#   boolean_policy {
#     enforced = true
#   }
# }

# Monitoring and alerting service account
resource "google_service_account" "monitoring" {
  account_id   = "${var.app_name}-monitoring-${var.environment}"
  display_name = "Monitoring service account for ${var.app_name}"
  description  = "Service account for monitoring and alerting"
}

resource "google_project_iam_member" "monitoring_permissions" {
  for_each = toset([
    "roles/monitoring.viewer",
    "roles/logging.viewer",
    "roles/storage.objectViewer"
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.monitoring.email}"
}
