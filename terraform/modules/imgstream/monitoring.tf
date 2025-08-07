# Cloud Monitoring configuration for ImgStream

# Notification channels
resource "google_monitoring_notification_channel" "email" {
  display_name = "ImgStream Operations Email - ${var.environment}"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }

  enabled = true
}

resource "google_monitoring_notification_channel" "slack" {
  count = var.slack_webhook_url != "" ? 1 : 0

  display_name = "ImgStream Slack Alerts - ${var.environment}"
  type         = "slack"

  labels = {
    channel_name = "#imgstream-alerts-${var.environment}"
    url          = var.slack_webhook_url
  }

  enabled = true
}

# Alert policies
resource "google_monitoring_alert_policy" "service_availability" {
  display_name = "ImgStream Service Availability - ${var.environment}"
  combiner     = "OR"
  enabled      = true

  documentation {
    content = "This alert fires when the ImgStream Cloud Run service availability drops below 99%. Check service logs and recent deployments."
  }

  conditions {
    display_name = "Service availability below 99%"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"imgstream-${var.environment}\" AND metric.type=\"run.googleapis.com/request_count\""
      duration        = "300s"
      comparison      = "COMPARISON_LT"
      threshold_value = 0.99

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = concat(
    [google_monitoring_notification_channel.email.name],
    var.slack_webhook_url != "" ? [google_monitoring_notification_channel.slack[0].name] : []
  )

  alert_strategy {
    auto_close = "1800s"
  }
}

resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "ImgStream High Error Rate - ${var.environment}"
  combiner     = "OR"
  enabled      = true

  documentation {
    content = "This alert fires when the error rate exceeds 5% over a 5-minute period. Check application logs and dependencies."
  }

  conditions {
    display_name = "Error rate above 5%"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"imgstream-${var.environment}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = concat(
    [google_monitoring_notification_channel.email.name],
    var.slack_webhook_url != "" ? [google_monitoring_notification_channel.slack[0].name] : []
  )
}

resource "google_monitoring_alert_policy" "high_response_time" {
  display_name = "ImgStream High Response Time - ${var.environment}"
  combiner     = "OR"
  enabled      = true

  documentation {
    content = "This alert fires when the 95th percentile response time exceeds 2 seconds. Check resource utilization and performance."
  }

  conditions {
    display_name = "95th percentile response time above 2s"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"imgstream-${var.environment}\" AND metric.type=\"run.googleapis.com/request_latencies\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 2000

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_PERCENTILE_95"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = concat(
    [google_monitoring_notification_channel.email.name],
    var.slack_webhook_url != "" ? [google_monitoring_notification_channel.slack[0].name] : []
  )
}

resource "google_monitoring_alert_policy" "high_memory_usage" {
  display_name = "ImgStream High Memory Usage - ${var.environment}"
  combiner     = "OR"
  enabled      = true

  documentation {
    content = "This alert fires when memory utilization exceeds 80%. Check for memory leaks and consider increasing memory limits."
  }

  conditions {
    display_name = "Memory utilization above 80%"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"imgstream-${var.environment}\" AND metric.type=\"run.googleapis.com/container/memory/utilizations\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = concat(
    [google_monitoring_notification_channel.email.name],
    var.slack_webhook_url != "" ? [google_monitoring_notification_channel.slack[0].name] : []
  )
}

resource "google_monitoring_alert_policy" "high_cpu_usage" {
  display_name = "ImgStream High CPU Usage - ${var.environment}"
  combiner     = "OR"
  enabled      = true

  documentation {
    content = "This alert fires when CPU utilization exceeds 80%. Check for CPU-intensive operations and consider increasing CPU allocation."
  }

  conditions {
    display_name = "CPU utilization above 80%"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"imgstream-${var.environment}\" AND metric.type=\"run.googleapis.com/container/cpu/utilizations\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = concat(
    [google_monitoring_notification_channel.email.name],
    var.slack_webhook_url != "" ? [google_monitoring_notification_channel.slack[0].name] : []
  )
}

resource "google_monitoring_alert_policy" "storage_usage" {
  display_name = "ImgStream High Storage Usage - ${var.environment}"
  combiner     = "OR"
  enabled      = true

  documentation {
    content = "This alert fires when GCS bucket usage exceeds the configured threshold. Review storage usage and implement cleanup policies."
  }

  conditions {
    display_name = "GCS bucket usage above threshold"

    condition_threshold {
      filter          = "resource.type=\"gcs_bucket\" AND resource.labels.bucket_name=\"${google_storage_bucket.photos.name}\" AND metric.type=\"storage.googleapis.com/storage/total_bytes\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.storage_alert_threshold_bytes

      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.bucket_name"]
      }
    }
  }

  notification_channels = concat(
    [google_monitoring_notification_channel.email.name],
    var.slack_webhook_url != "" ? [google_monitoring_notification_channel.slack[0].name] : []
  )
}

resource "google_monitoring_alert_policy" "instance_scaling" {
  display_name = "ImgStream Instance Scaling - ${var.environment}"
  combiner     = "OR"
  enabled      = true

  documentation {
    content = "This alert fires when the number of instances approaches the maximum limit. Review traffic patterns and scaling configuration."
  }

  conditions {
    display_name = "Instance count near maximum"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"imgstream-${var.environment}\" AND metric.type=\"run.googleapis.com/container/instance_count\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.max_instances * 0.8 # 80% of max instances

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = concat(
    [google_monitoring_notification_channel.email.name],
    var.slack_webhook_url != "" ? [google_monitoring_notification_channel.slack[0].name] : []
  )
}

# Monitoring Dashboard
resource "google_monitoring_dashboard" "imgstream_overview" {
  dashboard_json = jsonencode({
    displayName = "ImgStream Overview - ${var.environment}"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Request Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"imgstream-${var.environment}\" AND metric.type=\"run.googleapis.com/request_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["resource.labels.service_name"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              timeshiftDuration = "0s"
              yAxis = {
                label = "Requests/sec"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          width  = 6
          height = 4
          xPos   = 6
          widget = {
            title = "Error Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"imgstream-${var.environment}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["resource.labels.service_name"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              timeshiftDuration = "0s"
              yAxis = {
                label = "Errors/sec"
                scale = "LINEAR"
              }
            }
          }
        }
      ]
    }
  })
}
