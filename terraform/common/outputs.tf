# Common outputs for GitHub OIDC configuration

output "workload_identity_provider" {
  description = "The full name of the workload identity provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}

output "github_actions_service_account_email" {
  description = "Email of the GitHub Actions service account"
  value       = google_service_account.github_actions.email
}

# Artifact Registry outputs
output "artifact_registry_repository_url" {
  description = "URL of the shared Artifact Registry repository"
  value       = "${google_artifact_registry_repository.imgstream.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.imgstream.repository_id}"
}

output "artifact_registry_location" {
  description = "Location of the Artifact Registry repository"
  value       = google_artifact_registry_repository.imgstream.location
}

output "artifact_registry_repository_id" {
  description = "Repository ID of the Artifact Registry"
  value       = google_artifact_registry_repository.imgstream.repository_id
}
