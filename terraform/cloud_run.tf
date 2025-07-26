# Cloud Run service configuration for imgstream

# Cloud Run service
resource "google_cloud_run_v2_service" "imgstream" {
  name     = "${var.app_name}-${var.environment}"
  location = var.region
  
  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = true
  }

  template {
    # Service account for the container
    service_account = google_service_account.cloud_run.email
    
    # Scaling configuration
    scaling {
      min_instance_count = var.environment == "prod" ? 1 : 0
      max_instance_count = var.environment == "prod" ? 10 : 3
    }

    # Container configuration
    containers {
      # Container image (will be updated via CI/CD)
      image = var.container_image

      # Resource limits (optimized for free tier)
      resources {
        limits = {
          cpu    = var.environment == "prod" ? "1000m" : "1000m"  # 1 vCPU
          memory = var.environment == "prod" ? "2Gi" : "1Gi"      # 1-2GB RAM
        }
        
        # CPU is only allocated during request processing
        cpu_idle = false
        startup_cpu_boost = true
      }

      # Container port
      ports {
        container_port = 8080
        name          = "http1"
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

      env {
        name  = "PORT"
        value = "8080"
      }

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

      # Secrets from Secret Manager
      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app_secrets[env.key].secret_id
              version = "latest"
            }
          }
        }
      }

      # Health check configuration
      startup_probe {
        http_get {
          path = "/_stcore/health"
          port = 8080
        }
        initial_delay_seconds = 30
        timeout_seconds      = 10
        period_seconds       = 10
        failure_threshold    = 3
      }

      liveness_probe {
        http_get {
          path = "/_stcore/health"
          port = 8080
        }
        initial_delay_seconds = 60
        timeout_seconds      = 10
        period_seconds       = 30
        failure_threshold    = 3
      }
    }

    # Timeout configuration
    timeout = "300s"  # 5 minutes

    # Execution environment
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    # VPC connector (if needed for private resources)
    # vpc_access {
    #   connector = google_vpc_access_connector.connector.id
    #   egress    = "PRIVATE_RANGES_ONLY"
    # }
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

  # Annotations for Cloud Run specific settings
  annotations = {
    "run.googleapis.com/ingress"        = "all"
    "run.googleapis.com/ingress-status" = "all"
  }

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
