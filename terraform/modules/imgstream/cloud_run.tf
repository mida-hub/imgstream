# Cloud Run service configuration for imgstream

# Cloud Run service
resource "google_cloud_run_v2_service" "imgstream" {
  name     = "${var.app_name}-${var.environment}"
  location = var.region

  template {
    # Service account for the container
    service_account = google_service_account.cloud_run.email

    # Scaling configuration
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Container configuration
    containers {
      # Container image from shared Artifact Registry
      image = local.container_image

      # Resource limits
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }

        # CPU is only allocated during request processing
        cpu_idle          = false
        startup_cpu_boost = true
      }

      # Container port
      ports {
        container_port = 8080
        name           = "http1"
      }

      # Environment variables
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "PYTHONPATH"
        value = "/app/src"
      }

      # Note: PORT is automatically set by Cloud Run v2

      env {
        name  = "STREAMLIT_SERVER_PORT"
        value = "8080"
      }

      env {
        name  = "STREAMLIT_SERVER_ADDRESS"
        value = "0.0.0.0"
      }

      env {
        name  = "STREAMLIT_SERVER_HEADLESS"
        value = "true"
      }

      env {
        name  = "STREAMLIT_BROWSER_GATHER_USAGE_STATS"
        value = "false"
      }

      # GCS bucket names from storage resources
      env {
        name  = "GCS_PHOTOS_BUCKET"
        value = google_storage_bucket.photos.name
      }

      env {
        name  = "GCS_DATABASE_BUCKET"
        value = google_storage_bucket.database.name
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      # Streamlit secrets as environment variables
      env {
        name  = "STREAMLIT_SECRETS_GENERAL_DEBUG"
        value = var.environment == "dev" ? "true" : "false"
      }

      env {
        name  = "STREAMLIT_SECRETS_GENERAL_ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "STREAMLIT_SECRETS_DEV_AUTH_ENABLED"
        value = var.environment == "dev" ? "true" : "false"
      }

      env {
        name  = "STREAMLIT_SECRETS_DEV_AUTH_DEFAULT_EMAIL"
        value = "developer@example.com"
      }

      env {
        name  = "STREAMLIT_SECRETS_DEV_AUTH_DEFAULT_NAME"
        value = "Cloud Run Developer"
      }

      env {
        name  = "STREAMLIT_SECRETS_DEV_AUTH_DEFAULT_USER_ID"
        value = "cloudrun-dev-001"
      }

      # Health check configuration
      startup_probe {
        http_get {
          path = "/_stcore/health"
          port = 8080
        }
        initial_delay_seconds = 60
        timeout_seconds       = 10
        period_seconds        = 15
        failure_threshold     = 5
      }

      liveness_probe {
        http_get {
          path = "/_stcore/health"
          port = 8080
        }
        initial_delay_seconds = 120
        timeout_seconds       = 30
        period_seconds        = 60
        failure_threshold     = 3
      }
    }

    # Timeout configuration
    timeout = "300s" # 5 minutes

    # Execution environment
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
  }

  # Traffic configuration
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  # Labels for resource management
  labels = {
    environment = var.environment
    app         = var.app_name
    managed-by  = "terraform"
  }

  # Note: Cloud Run v2 doesn't support system annotations like ingress
  # These are managed automatically by the service

  depends_on = [
    google_project_service.required_apis,
    google_storage_bucket.photos,
    google_storage_bucket.database,
    google_service_account.cloud_run
  ]
}

# IAM policy for Cloud Run service
resource "google_cloud_run_v2_service_iam_binding" "public_access" {
  count = var.enable_public_access && !var.enable_iap ? 1 : 0

  location = google_cloud_run_v2_service.imgstream.location
  name     = google_cloud_run_v2_service.imgstream.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}

# IAM policy for IAP access (when IAP is enabled)
resource "google_cloud_run_v2_service_iam_binding" "iap_access" {
  count = var.enable_iap ? 1 : 0

  location = google_cloud_run_v2_service.imgstream.location
  name     = google_cloud_run_v2_service.imgstream.name
  role     = "roles/run.invoker"
  members  = ["serviceAccount:service-${data.google_project.current.number}@gcp-sa-iap.iam.gserviceaccount.com"]
}

# IAM policy for authenticated access (when neither public nor IAP is enabled)
resource "google_cloud_run_v2_service_iam_binding" "authenticated_access" {
  count = !var.enable_public_access && !var.enable_iap ? 1 : 0

  location = google_cloud_run_v2_service.imgstream.location
  name     = google_cloud_run_v2_service.imgstream.name
  role     = "roles/run.invoker"
  members  = ["serviceAccount:${google_service_account.cloud_run.email}"]
}

# Custom domain mapping (optional)
resource "google_cloud_run_domain_mapping" "imgstream" {
  count = var.custom_domain != "" ? 1 : 0

  location = var.region
  name     = var.custom_domain

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.imgstream.name
  }
}
