# Secret Manager configuration for imgstream

# Secret Manager secrets
resource "google_secret_manager_secret" "app_secrets" {
  for_each = var.secret_env_vars

  secret_id = "${var.app_name}-${var.environment}-${each.key}"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = var.app_name
    managed-by  = "terraform"
  }
}

# Secret versions (initial empty values - to be updated manually or via CI/CD)
resource "google_secret_manager_secret_version" "app_secret_versions" {
  for_each = var.secret_env_vars

  secret      = google_secret_manager_secret.app_secrets[each.key].id
  secret_data = each.value
}

# IAM permissions for Cloud Run service account to access secrets
resource "google_secret_manager_secret_iam_member" "cloud_run_secret_access" {
  for_each = var.secret_env_vars

  secret_id = google_secret_manager_secret.app_secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Example secrets for different environments
locals {
  default_secrets = {
    # Database encryption key
    "DB_ENCRYPTION_KEY" = var.environment == "prod" ? "CHANGE_ME_IN_PRODUCTION" : "dev-encryption-key-123"
    
    # Session secret for Streamlit
    "SESSION_SECRET" = var.environment == "prod" ? "CHANGE_ME_IN_PRODUCTION" : "dev-session-secret-456"
    
    # Optional: External API keys
    # "EXTERNAL_API_KEY" = var.environment == "prod" ? "CHANGE_ME_IN_PRODUCTION" : "dev-api-key"
  }
}

# Create default secrets if not provided
resource "google_secret_manager_secret" "default_secrets" {
  for_each = var.create_default_secrets ? local.default_secrets : {}

  secret_id = "${var.app_name}-${var.environment}-${each.key}"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = var.app_name
    managed-by  = "terraform"
    type        = "default"
  }
}

resource "google_secret_manager_secret_version" "default_secret_versions" {
  for_each = var.create_default_secrets ? local.default_secrets : {}

  secret      = google_secret_manager_secret.default_secrets[each.key].id
  secret_data = each.value
}

resource "google_secret_manager_secret_iam_member" "cloud_run_default_secret_access" {
  for_each = var.create_default_secrets ? local.default_secrets : {}

  secret_id = google_secret_manager_secret.default_secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}
