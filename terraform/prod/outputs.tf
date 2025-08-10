# Outputs for production environment

# GitHub OIDC outputs (from common state)
output "workload_identity_provider" {
  description = "The full name of the workload identity provider for GitHub Actions"
  value       = data.terraform_remote_state.common.outputs.workload_identity_provider
}

output "github_actions_service_account_email" {
  description = "Email of the GitHub Actions service account"
  value       = data.terraform_remote_state.common.outputs.github_actions_service_account_email
}

# ImgStream application outputs
output "cloud_run_service_url" {
  description = "URL of the Cloud Run service"
  value       = module.imgstream.cloud_run_service_url
}

output "cloud_run_service_name" {
  description = "Name of the Cloud Run service"
  value       = module.imgstream.cloud_run_service_name
}

output "photos_bucket_name" {
  description = "Name of the photos storage bucket"
  value       = module.imgstream.photos_bucket_name
}

output "database_bucket_name" {
  description = "Name of the database backup bucket"
  value       = module.imgstream.database_bucket_name
}

output "artifact_registry_repository_url" {
  description = "URL of the Artifact Registry repository"
  value       = data.terraform_remote_state.common.outputs.artifact_registry_repository_url
}

output "cloud_run_service_account_email" {
  description = "Email of the Cloud Run service account"
  value       = module.imgstream.cloud_run_service_account_email
}

output "monitoring_dashboard_url" {
  description = "URL to the monitoring dashboard"
  value       = module.imgstream.monitoring_dashboard_url
}

output "notification_channels" {
  description = "Created notification channels"
  value       = module.imgstream.notification_channels
}
