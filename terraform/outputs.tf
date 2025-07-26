# Outputs for imgstream infrastructure

output "photos_bucket_name" {
  description = "Name of the photos storage bucket"
  value       = google_storage_bucket.photos.name
}

output "photos_bucket_url" {
  description = "URL of the photos storage bucket"
  value       = google_storage_bucket.photos.url
}

output "database_bucket_name" {
  description = "Name of the database backup bucket"
  value       = google_storage_bucket.database.name
}

output "database_bucket_url" {
  description = "URL of the database backup bucket"
  value       = google_storage_bucket.database.url
}

output "project_id" {
  description = "The GCP project ID"
  value       = var.project_id
}

output "region" {
  description = "The GCP region"
  value       = var.region
}

output "service_account_email" {
  description = "Email of the Cloud Run service account"
  value       = google_service_account.cloud_run.email
}

output "cloud_run_service_name" {
  description = "Name of the Cloud Run service"
  value       = google_cloud_run_v2_service.imgstream.name
}

output "cloud_run_service_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.imgstream.uri
}

output "cloud_run_service_location" {
  description = "Location of the Cloud Run service"
  value       = google_cloud_run_v2_service.imgstream.location
}

output "secret_names" {
  description = "Names of created secrets"
  value = merge(
    { for k, v in google_secret_manager_secret.app_secrets : k => v.secret_id },
    var.create_default_secrets ? { for k, v in google_secret_manager_secret.default_secrets : k => v.secret_id } : {}
  )
}
