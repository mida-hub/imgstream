# Outputs for ImgStream module

output "cloud_run_service_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.imgstream.uri
}

output "cloud_run_service_name" {
  description = "Name of the Cloud Run service"
  value       = google_cloud_run_v2_service.imgstream.name
}

output "photos_bucket_name" {
  description = "Name of the photos storage bucket"
  value       = google_storage_bucket.photos.name
}

output "database_bucket_name" {
  description = "Name of the database backup bucket"
  value       = google_storage_bucket.database.name
}

output "cloud_run_service_account_email" {
  description = "Email of the Cloud Run service account"
  value       = google_service_account.cloud_run.email
}

output "monitoring_dashboard_url" {
  description = "URL to the monitoring dashboard"
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${google_monitoring_dashboard.imgstream_overview.id}?project=${var.project_id}"
}

output "notification_channels" {
  description = "Created notification channels"
  value = {
    email = google_monitoring_notification_channel.email.name
    slack = var.slack_webhook_url != "" ? google_monitoring_notification_channel.slack[0].name : null
  }
}
