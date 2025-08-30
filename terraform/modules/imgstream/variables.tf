# Variables for ImgStream infrastructure module

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "asia-northeast1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "imgstream"
}

variable "bucket_location" {
  description = "Location for GCS buckets"
  type        = string
  default     = "ASIA"
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

variable "allowed_users" {
  description = "List of allowed user emails for IAP authentication"
  type        = list(string)
  default     = []
}

variable "custom_domain" {
  description = "Custom domain for Cloud Run service"
  type        = string
  default     = ""
}

variable "container_image" {
  description = "Container image for Cloud Run service (deprecated - use container_image_tag instead)"
  type        = string
  default     = "gcr.io/cloudrun/hello"
}

variable "container_image_tag" {
  description = "Container image tag for the environment (overrides default environment tag)"
  type        = string
  default     = null
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 1
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

variable "enable_iap" {
  description = "Enable Cloud IAP for the application"
  type        = bool
  default     = true
}

variable "rate_limit_requests_per_minute" {
  description = "Rate limit requests per minute per IP"
  type        = number
  default     = 100
}

variable "alert_email" {
  description = "Email address for alert notifications"
  type        = string
  default     = "ops@example.com"
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = ""
}

variable "storage_alert_threshold_bytes" {
  description = "Storage usage threshold in bytes for alerts"
  type        = number
  default     = 85899345920 # 80GB
}

variable "client_version" {
  type    = string
  default = "535.0.0"
}
