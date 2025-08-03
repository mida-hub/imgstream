# Common outputs for GitHub OIDC configuration

output "workload_identity_provider" {
  description = "The full name of the workload identity provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}

output "github_actions_service_account_email" {
  description = "Email of the GitHub Actions service account"
  value       = google_service_account.github_actions.email
}
