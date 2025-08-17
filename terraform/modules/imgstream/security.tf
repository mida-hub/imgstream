# Security and access control configurations

# Cloud Run service account permissions
resource "google_project_iam_member" "cloud_run_permissions" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
    "roles/iam.serviceAccountTokenCreator",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

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
