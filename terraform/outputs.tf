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
