resource "google_service_account" "cloud_run" {
  account_id   = "${local.app_name}-cloud-run-${local.environment}"
  display_name = "Cloud Run service account for ${local.app_name}"
  description  = "Service account used by Cloud Run for ${local.app_name} application"
}

resource "google_storage_bucket_iam_member" "cloud_run" {
  bucket = google_storage_bucket.local.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_permissions" {
  for_each = toset([
    "roles/iam.serviceAccountTokenCreator",
  ])

  project = "apps-466614"
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_service_account_key" "cloud_run" {
  service_account_id = google_service_account.cloud_run.name
}

# 生成された秘密鍵をローカルファイルに保存
# ファイル名は "sa-key.json" となります
resource "local_file" "service_account_key" {
  content              = base64decode(google_service_account_key.cloud_run.private_key)
  filename             = "./output/secrets/sa-key-${local.app_name}-cloud-run-${local.environment}.json"
  file_permission      = "0600"
  directory_permission = "0755"
}
