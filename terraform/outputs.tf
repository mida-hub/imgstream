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

output "load_balancer_ip" {
  description = "Static IP address of the load balancer"
  value       = var.enable_iap ? google_compute_global_address.imgstream_ip[0].address : null
}

output "iap_client_id" {
  description = "IAP OAuth client ID"
  value       = var.enable_iap ? google_iap_client.project_client[0].client_id : null
  sensitive   = true
}

output "iap_client_secret" {
  description = "IAP OAuth client secret"
  value       = var.enable_iap ? google_iap_client.project_client[0].secret : null
  sensitive   = true
}

output "backend_service_name" {
  description = "Name of the backend service"
  value       = var.enable_iap ? google_compute_backend_service.imgstream_backend[0].name : null
}

output "ssl_certificate_name" {
  description = "Name of the SSL certificate"
  value       = var.enable_iap && var.custom_domain != "" ? google_compute_managed_ssl_certificate.imgstream_ssl_cert[0].name : null
}

output "application_url" {
  description = "Application URL (with custom domain if configured)"
  value       = var.enable_iap ? (var.custom_domain != "" ? "https://${var.custom_domain}" : "https://${google_compute_global_address.imgstream_ip[0].address}") : google_cloud_run_v2_service.imgstream.uri
}

output "iap_enabled" {
  description = "Whether IAP is enabled"
  value       = var.enable_iap
}
