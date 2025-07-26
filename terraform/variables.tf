# Variables for imgstream infrastructure

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "imgstream"
}

variable "bucket_location" {
  description = "Location for GCS buckets"
  type        = string
  default     = "US"
}

variable "lifecycle_coldline_days" {
  description = "Days after which objects transition to Coldline storage"
  type        = number
  default     = 30
}

variable "lifecycle_archive_days" {
  description = "Days after which objects transition to Archive storage"
  type        = number
  default     = 365
}

variable "lifecycle_delete_days" {
  description = "Days after which objects are deleted (0 = never delete)"
  type        = number
  default     = 0
}

variable "allowed_domains" {
  description = "List of allowed domains for IAP authentication"
  type        = list(string)
  default     = []
}

variable "allowed_users" {
  description = "List of allowed user emails for IAP authentication"
  type        = list(string)
  default     = []
}

# Cloud Run configuration
variable "container_image" {
  description = "Container image for Cloud Run service"
  type        = string
  default     = "gcr.io/cloudrun/hello"  # Placeholder image
}

variable "enable_public_access" {
  description = "Enable public access to Cloud Run service (disable for IAP)"
  type        = bool
  default     = false
}

variable "custom_domain" {
  description = "Custom domain for Cloud Run service"
  type        = string
  default     = ""
}

variable "secret_env_vars" {
  description = "Environment variables to store as secrets"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "create_default_secrets" {
  description = "Create default secrets for the application"
  type        = bool
  default     = true
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "cpu_limit" {
  description = "CPU limit for containers"
  type        = string
  default     = "1000m"
}

variable "memory_limit" {
  description = "Memory limit for containers"
  type        = string
  default     = "2Gi"
}

# IAP configuration
variable "iap_support_email" {
  description = "Support email for IAP OAuth consent screen"
  type        = string
}

variable "enable_iap" {
  description = "Enable Cloud IAP for the application"
  type        = bool
  default     = true
}

variable "enable_security_policy" {
  description = "Enable Cloud Armor security policy"
  type        = bool
  default     = true
}

variable "enable_waf_rules" {
  description = "Enable WAF rules in security policy"
  type        = bool
  default     = true
}

variable "rate_limit_requests_per_minute" {
  description = "Rate limit requests per minute per IP"
  type        = number
  default     = 100
}

variable "allowed_countries" {
  description = "List of allowed country codes (ISO 3166-1 alpha-2)"
  type        = list(string)
  default     = []
}

variable "session_duration" {
  description = "IAP session duration in seconds"
  type        = number
  default     = 3600  # 1 hour
}
