# Secret Manager configuration for imgstream
# 
# This file is reserved for future secret management needs.
# Currently, the ImgStream application does not require any secrets
# as it uses:
# - Google Cloud IAP for authentication (no custom session secrets needed)
# - DuckDB without encryption (no database encryption keys needed)
# - Standard Streamlit session management (no custom session secrets needed)
#
# If you need to add secrets in the future, you can use the following pattern:
#
# resource "google_secret_manager_secret" "app_secrets" {
#   for_each = var.secret_env_vars
#
#   secret_id = "${var.app_name}-${var.environment}-${each.key}"
#
#   replication {
#     auto {}
#   }
#
#   labels = {
#     environment = var.environment
#     app         = var.app_name
#     managed-by  = "terraform"
#   }
# }
#
# resource "google_secret_manager_secret_version" "app_secret_versions" {
#   for_each = var.secret_env_vars
#
#   secret      = google_secret_manager_secret.app_secrets[each.key].id
#   secret_data = each.value
# }
#
# resource "google_secret_manager_secret_iam_member" "cloud_run_secret_access" {
#   for_each = var.secret_env_vars
#
#   secret_id = google_secret_manager_secret.app_secrets[each.key].secret_id
#   role      = "roles/secretmanager.secretAccessor"
#   member    = "serviceAccount:${google_service_account.cloud_run.email}"
# }
