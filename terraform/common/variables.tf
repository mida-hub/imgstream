# Common variables for GitHub OIDC configuration

variable "project_id" {
  description = "The GCP project ID"
  type        = string
  default     = "apps-466614"
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "asia-northeast1"
}

variable "github_repository" {
  description = "GitHub repository in the format 'owner/repo' for OIDC authentication"
  type        = string
  default     = "mida-hub/imgstream"
}

# Artifact Registry configuration
variable "cloud_run_service_accounts" {
  description = "List of Cloud Run service account emails that need access to the Artifact Registry"
  type        = list(string)
  default     = []
}
