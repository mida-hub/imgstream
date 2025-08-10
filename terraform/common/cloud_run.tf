resource "google_iap_web_iam_member" "iap_access" {
  role   = "roles/iap.httpsResourceAccessor"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-iap.iam.gserviceaccount.com"
}
