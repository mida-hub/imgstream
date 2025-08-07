# Cloud IAP (Identity-Aware Proxy) configuration for imgstream

# OAuth consent screen configuration
resource "google_iap_brand" "project_brand" {
  count = var.enable_iap ? 1 : 0

  support_email     = var.iap_support_email
  application_title = "${var.app_name} - ${var.environment}"
  project           = var.project_id
}

# OAuth client for IAP
resource "google_iap_client" "project_client" {
  count = var.enable_iap ? 1 : 0

  display_name = "${var.app_name}-${var.environment}-iap-client"
  brand        = google_iap_brand.project_brand[0].name
}

# Backend service for Cloud Run
resource "google_compute_backend_service" "imgstream_backend" {
  count = var.enable_iap ? 1 : 0

  name                  = "${var.app_name}-${var.environment}-backend"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 300

  backend {
    group = google_compute_region_network_endpoint_group.imgstream_neg[0].id
  }

  # Health check
  health_checks = [google_compute_health_check.imgstream_health_check[0].id]

  # IAP configuration
  iap {
    enabled              = true
    oauth2_client_id     = google_iap_client.project_client[0].client_id
    oauth2_client_secret = google_iap_client.project_client[0].secret
  }

  # Security settings
  security_policy = var.enable_security_policy ? google_compute_security_policy.imgstream_security_policy[0].id : null

  # Custom request headers
  custom_request_headers = [
    "X-Client-Region:{client_region}",
    "X-Client-City:{client_city}",
    "X-Client-Country:{client_country}"
  ]

  depends_on = [
    google_project_service.required_apis,
    google_cloud_run_v2_service.imgstream
  ]
}

# Network Endpoint Group for Cloud Run
resource "google_compute_region_network_endpoint_group" "imgstream_neg" {
  count = var.enable_iap ? 1 : 0

  name                  = "${var.app_name}-${var.environment}-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = google_cloud_run_v2_service.imgstream.name
  }
}

# Health check for backend service
resource "google_compute_health_check" "imgstream_health_check" {
  count = var.enable_iap ? 1 : 0

  name                = "${var.app_name}-${var.environment}-health-check"
  check_interval_sec  = 30
  timeout_sec         = 10
  healthy_threshold   = 2
  unhealthy_threshold = 3

  http_health_check {
    port         = 8080
    request_path = "/_stcore/health"
  }
}

# URL map for load balancer
resource "google_compute_url_map" "imgstream_url_map" {
  count = var.enable_iap ? 1 : 0

  name            = "${var.app_name}-${var.environment}-url-map"
  default_service = google_compute_backend_service.imgstream_backend[0].id

  # Host rules for custom domain
  dynamic "host_rule" {
    for_each = var.custom_domain != "" ? [1] : []
    content {
      hosts        = [var.custom_domain]
      path_matcher = "allpaths"
    }
  }

  dynamic "path_matcher" {
    for_each = var.custom_domain != "" ? [1] : []
    content {
      name            = "allpaths"
      default_service = google_compute_backend_service.imgstream_backend[0].id
    }
  }
}

# SSL certificate for HTTPS
resource "google_compute_managed_ssl_certificate" "imgstream_ssl_cert" {
  count = var.enable_iap && var.custom_domain != "" ? 1 : 0
  name  = "${var.app_name}-${var.environment}-ssl-cert"

  managed {
    domains = [var.custom_domain]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# HTTPS proxy
resource "google_compute_target_https_proxy" "imgstream_https_proxy" {
  count = var.enable_iap ? 1 : 0

  name             = "${var.app_name}-${var.environment}-https-proxy"
  url_map          = google_compute_url_map.imgstream_url_map[0].id
  ssl_certificates = var.custom_domain != "" ? [google_compute_managed_ssl_certificate.imgstream_ssl_cert[0].id] : []

  # Security headers
  quic_override = "ENABLE"
}

# HTTP to HTTPS redirect
resource "google_compute_url_map" "imgstream_http_redirect" {
  count = var.enable_iap ? 1 : 0

  name = "${var.app_name}-${var.environment}-http-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "imgstream_http_proxy" {
  count = var.enable_iap ? 1 : 0

  name    = "${var.app_name}-${var.environment}-http-proxy"
  url_map = google_compute_url_map.imgstream_http_redirect[0].id
}

# Global forwarding rules
resource "google_compute_global_forwarding_rule" "imgstream_https_forwarding_rule" {
  count = var.enable_iap ? 1 : 0

  name       = "${var.app_name}-${var.environment}-https-forwarding-rule"
  target     = google_compute_target_https_proxy.imgstream_https_proxy[0].id
  port_range = "443"
  ip_address = google_compute_global_address.imgstream_ip[0].address
}

resource "google_compute_global_forwarding_rule" "imgstream_http_forwarding_rule" {
  count = var.enable_iap ? 1 : 0

  name       = "${var.app_name}-${var.environment}-http-forwarding-rule"
  target     = google_compute_target_http_proxy.imgstream_http_proxy[0].id
  port_range = "80"
  ip_address = google_compute_global_address.imgstream_ip[0].address
}

# Static IP address
resource "google_compute_global_address" "imgstream_ip" {
  count = var.enable_iap ? 1 : 0

  name = "${var.app_name}-${var.environment}-ip"
}

# Security policy (optional)
resource "google_compute_security_policy" "imgstream_security_policy" {
  count = var.enable_iap && var.enable_security_policy ? 1 : 0
  name  = "${var.app_name}-${var.environment}-security-policy"

  # Default rule
  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default allow rule"
  }

  # Rate limiting rule
  rule {
    action   = "rate_based_ban"
    priority = "1000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.rate_limit_requests_per_minute
        interval_sec = 60
      }
      ban_duration_sec = 300 # 5 minutes
    }
    description = "Rate limiting rule"
  }

  # Block common attack patterns
  dynamic "rule" {
    for_each = var.enable_waf_rules ? [1] : []
    content {
      action   = "deny(403)"
      priority = "900"
      match {
        expr {
          expression = "evaluatePreconfiguredExpr('xss-stable')"
        }
      }
      description = "Block XSS attacks"
    }
  }

  dynamic "rule" {
    for_each = var.enable_waf_rules ? [1] : []
    content {
      action   = "deny(403)"
      priority = "901"
      match {
        expr {
          expression = "evaluatePreconfiguredExpr('sqli-stable')"
        }
      }
      description = "Block SQL injection attacks"
    }
  }

  # Geographic restrictions (if specified)
  dynamic "rule" {
    for_each = length(var.allowed_countries) > 0 ? [1] : []
    content {
      action   = "deny(403)"
      priority = "800"
      match {
        expr {
          expression = "origin.region_code not in ${jsonencode(var.allowed_countries)}"
        }
      }
      description = "Geographic access restriction"
    }
  }
}

# IAP access control
resource "google_iap_web_iam_binding" "iap_users" {
  count = var.enable_iap && length(var.allowed_users) > 0 ? 1 : 0

  project = var.project_id
  role    = "roles/iap.httpsResourceAccessor"
  members = [for user in var.allowed_users : "user:${user}"]

  depends_on = [google_compute_backend_service.imgstream_backend]
}

resource "google_iap_web_iam_binding" "iap_domains" {
  count = var.enable_iap && length(var.allowed_domains) > 0 ? 1 : 0

  project = var.project_id
  role    = "roles/iap.httpsResourceAccessor"
  members = [for domain in var.allowed_domains : "domain:${domain}"]

  depends_on = [google_compute_backend_service.imgstream_backend]
}

# IAP settings
resource "google_iap_web_backend_service_iam_binding" "iap_backend_users" {
  count = var.enable_iap && length(var.allowed_users) > 0 ? 1 : 0

  project             = var.project_id
  web_backend_service = google_compute_backend_service.imgstream_backend[0].name
  role                = "roles/iap.httpsResourceAccessor"
  members             = [for user in var.allowed_users : "user:${user}"]
}

resource "google_iap_web_backend_service_iam_binding" "iap_backend_domains" {
  count = var.enable_iap && length(var.allowed_domains) > 0 ? 1 : 0

  project             = var.project_id
  web_backend_service = google_compute_backend_service.imgstream_backend[0].name
  role                = "roles/iap.httpsResourceAccessor"
  members             = [for domain in var.allowed_domains : "domain:${domain}"]
}
