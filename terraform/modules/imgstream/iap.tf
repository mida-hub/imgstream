resource "google_iap_web_iam_member" "iap_users" {
  for_each = var.enable_iap && length(var.allowed_users) > 0 ? toset(var.allowed_users) : []

  project = var.project_id
  role    = "roles/iap.httpsResourceAccessor"
  member  = "user:${each.key}"
}
