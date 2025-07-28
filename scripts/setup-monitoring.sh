#!/bin/bash

# Cloud Monitoring setup script for ImgStream
# This script creates alert policies, notification channels, and dashboards

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}\")\" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT=${ENVIRONMENT:-production}
PROJECT_ID=${GOOGLE_CLOUD_PROJECT}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate prerequisites
validate_prerequisites() {
    log_info "Validating prerequisites..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI not installed"
        exit 1
    fi
    
    # Check if project is set
    if [[ -z "$PROJECT_ID" ]]; then
        log_error "GOOGLE_CLOUD_PROJECT environment variable not set"
        exit 1
    fi
    
    # Check authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null; then
        log_error "No active gcloud authentication found"
        exit 1
    fi
    
    # Check required APIs
    local required_apis=("monitoring.googleapis.com" "logging.googleapis.com")
    
    for api in "${required_apis[@]}"; do
        if ! gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
            log_warning "Enabling required API: $api"
            gcloud services enable "$api"
        else
            log_success "API enabled: $api"
        fi
    done
    
    log_success "Prerequisites validated"
}

# Create notification channels
create_notification_channels() {
    log_info "Creating notification channels..."
    
    # Email notification channel
    local email_channel_config=$(cat <<EOF
{
  "type": "email",
  "displayName": "ImgStream Operations Team - ${ENVIRONMENT}",
  "description": "Email notifications for ImgStream ${ENVIRONMENT} environment",
  "labels": {
    "email_address": "${ALERT_EMAIL:-ops@example.com}"
  },
  "enabled": true
}
EOF
)
    
    # Create email notification channel
    local email_channel_name
    email_channel_name=$(gcloud alpha monitoring channels create \
        --channel-content="$email_channel_config" \
        --format="value(name)" 2>/dev/null || echo "")
    
    if [[ -n "$email_channel_name" ]]; then
        log_success "Created email notification channel: $email_channel_name"
        echo "$email_channel_name" > "/tmp/imgstream-email-channel-${ENVIRONMENT}.txt"
    else
        log_warning "Email notification channel may already exist or creation failed"
    fi
    
    # Slack notification channel (if webhook is provided)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local slack_channel_config=$(cat <<EOF
{
  "type": "slack",
  "displayName": "ImgStream Slack Alerts - ${ENVIRONMENT}",
  "description": "Slack notifications for ImgStream ${ENVIRONMENT} environment",
  "labels": {
    "channel_name": "#imgstream-alerts-${ENVIRONMENT}",
    "url": "${SLACK_WEBHOOK_URL}"
  },
  "enabled": true
}
EOF
)
        
        local slack_channel_name
        slack_channel_name=$(gcloud alpha monitoring channels create \
            --channel-content="$slack_channel_config" \
            --format="value(name)" 2>/dev/null || echo "")
        
        if [[ -n "$slack_channel_name" ]]; then
            log_success "Created Slack notification channel: $slack_channel_name"
            echo "$slack_channel_name" > "/tmp/imgstream-slack-channel-${ENVIRONMENT}.txt"
        else
            log_warning "Slack notification channel creation failed"
        fi
    else
        log_info "Skipping Slack notification channel (SLACK_WEBHOOK_URL not set)"
    fi
}

# Create alert policies
create_alert_policies() {
    log_info "Creating alert policies..."
    
    # Get notification channel names
    local email_channel=""
    local slack_channel=""
    
    if [[ -f "/tmp/imgstream-email-channel-${ENVIRONMENT}.txt" ]]; then
        email_channel=$(cat "/tmp/imgstream-email-channel-${ENVIRONMENT}.txt")
    fi
    
    if [[ -f "/tmp/imgstream-slack-channel-${ENVIRONMENT}.txt" ]]; then
        slack_channel=$(cat "/tmp/imgstream-slack-channel-${ENVIRONMENT}.txt")
    fi
    
    # Service availability alert
    create_service_availability_alert "$email_channel" "$slack_channel"
    
    # High error rate alert
    create_high_error_rate_alert "$email_channel" "$slack_channel"
    
    # High response time alert
    create_high_response_time_alert "$email_channel" "$slack_channel"
    
    # High memory usage alert
    create_high_memory_usage_alert "$email_channel" "$slack_channel"
    
    # High CPU usage alert
    create_high_cpu_usage_alert "$email_channel" "$slack_channel"
    
    # Storage usage alert
    create_storage_usage_alert "$email_channel" "$slack_channel"
    
    # Instance scaling alert
    create_instance_scaling_alert "$email_channel" "$slack_channel"
}

# Create service availability alert
create_service_availability_alert() {
    local email_channel="$1"
    local slack_channel="$2"
    
    local notification_channels=""
    if [[ -n "$email_channel" ]]; then
        notification_channels="\"$email_channel\""
    fi
    if [[ -n "$slack_channel" ]]; then
        if [[ -n "$notification_channels" ]]; then
            notification_channels="$notification_channels, \"$slack_channel\""
        else
            notification_channels="\"$slack_channel\""
        fi
    fi
    
    local alert_policy=$(cat <<EOF
{
  "displayName": "ImgStream Service Availability - ${ENVIRONMENT}",
  "documentation": {
    "content": "This alert fires when the ImgStream Cloud Run service availability drops below 99%. Check service logs and recent deployments."
  },
  "conditions": [
    {
      "displayName": "Service availability below 99%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/request_count\"",
        "comparison": "COMPARISON_LESS_THAN",
        "thresholdValue": 0.99,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_RATE",
            "crossSeriesReducer": "REDUCE_MEAN",
            "groupByFields": ["resource.labels.service_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": [$notification_channels],
  "alertStrategy": {
    "autoClose": "1800s"
  }
}
EOF
)
    
    if gcloud alpha monitoring policies create --policy-from-file=<(echo "$alert_policy") > /dev/null 2>&1; then
        log_success "Created service availability alert policy"
    else
        log_warning "Service availability alert policy creation failed or already exists"
    fi
}

# Create high error rate alert
create_high_error_rate_alert() {
    local email_channel="$1"
    local slack_channel="$2"
    
    local notification_channels=""
    if [[ -n "$email_channel" ]]; then
        notification_channels="\"$email_channel\""
    fi
    if [[ -n "$slack_channel" ]]; then
        if [[ -n "$notification_channels" ]]; then
            notification_channels="$notification_channels, \"$slack_channel\""
        else
            notification_channels="\"$slack_channel\""
        fi
    fi
    
    local alert_policy=$(cat <<EOF
{
  "displayName": "ImgStream High Error Rate - ${ENVIRONMENT}",
  "documentation": {
    "content": "This alert fires when the error rate exceeds 5% over a 5-minute period. Check application logs and dependencies."
  },
  "conditions": [
    {
      "displayName": "Error rate above 5%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.05,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_RATE",
            "crossSeriesReducer": "REDUCE_SUM",
            "groupByFields": ["resource.labels.service_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": [$notification_channels]
}
EOF
)
    
    if gcloud alpha monitoring policies create --policy-from-file=<(echo "$alert_policy") > /dev/null 2>&1; then
        log_success "Created high error rate alert policy"
    else
        log_warning "High error rate alert policy creation failed or already exists"
    fi
}

# Create high response time alert
create_high_response_time_alert() {
    local email_channel="$1"
    local slack_channel="$2"
    
    local notification_channels=""
    if [[ -n "$email_channel" ]]; then
        notification_channels="\"$email_channel\""
    fi
    if [[ -n "$slack_channel" ]]; then
        if [[ -n "$notification_channels" ]]; then
            notification_channels="$notification_channels, \"$slack_channel\""
        else
            notification_channels="\"$slack_channel\""
        fi
    fi
    
    local alert_policy=$(cat <<EOF
{
  "displayName": "ImgStream High Response Time - ${ENVIRONMENT}",
  "documentation": {
    "content": "This alert fires when the 95th percentile response time exceeds 2 seconds. Check resource utilization and performance."
  },
  "conditions": [
    {
      "displayName": "95th percentile response time above 2s",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/request_latencies\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 2000,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_DELTA",
            "crossSeriesReducer": "REDUCE_PERCENTILE_95",
            "groupByFields": ["resource.labels.service_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": [$notification_channels]
}
EOF
)
    
    if gcloud alpha monitoring policies create --policy-from-file=<(echo "$alert_policy") > /dev/null 2>&1; then
        log_success "Created high response time alert policy"
    else
        log_warning "High response time alert policy creation failed or already exists"
    fi
}

# Create high memory usage alert
create_high_memory_usage_alert() {
    local email_channel="$1"
    local slack_channel="$2"
    
    local notification_channels=""
    if [[ -n "$email_channel" ]]; then
        notification_channels="\"$email_channel\""
    fi
    if [[ -n "$slack_channel" ]]; then
        if [[ -n "$notification_channels" ]]; then
            notification_channels="$notification_channels, \"$slack_channel\""
        else
            notification_channels="\"$slack_channel\""
        fi
    fi
    
    local alert_policy=$(cat <<EOF
{
  "displayName": "ImgStream High Memory Usage - ${ENVIRONMENT}",
  "documentation": {
    "content": "This alert fires when memory utilization exceeds 80%. Check for memory leaks and consider increasing memory limits."
  },
  "conditions": [
    {
      "displayName": "Memory utilization above 80%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/container/memory/utilizations\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.8,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_MEAN",
            "groupByFields": ["resource.labels.service_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": [$notification_channels]
}
EOF
)
    
    if gcloud alpha monitoring policies create --policy-from-file=<(echo "$alert_policy") > /dev/null 2>&1; then
        log_success "Created high memory usage alert policy"
    else
        log_warning "High memory usage alert policy creation failed or already exists"
    fi
}

# Create high CPU usage alert
create_high_cpu_usage_alert() {
    local email_channel="$1"
    local slack_channel="$2"
    
    local notification_channels=""
    if [[ -n "$email_channel" ]]; then
        notification_channels="\"$email_channel\""
    fi
    if [[ -n "$slack_channel" ]]; then
        if [[ -n "$notification_channels" ]]; then
            notification_channels="$notification_channels, \"$slack_channel\""
        else
            notification_channels="\"$slack_channel\""
        fi
    fi
    
    local alert_policy=$(cat <<EOF
{
  "displayName": "ImgStream High CPU Usage - ${ENVIRONMENT}",
  "documentation": {
    "content": "This alert fires when CPU utilization exceeds 80%. Check for CPU-intensive operations and consider increasing CPU allocation."
  },
  "conditions": [
    {
      "displayName": "CPU utilization above 80%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/container/cpu/utilizations\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.8,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_MEAN",
            "groupByFields": ["resource.labels.service_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": [$notification_channels]
}
EOF
)
    
    if gcloud alpha monitoring policies create --policy-from-file=<(echo "$alert_policy") > /dev/null 2>&1; then
        log_success "Created high CPU usage alert policy"
    else
        log_warning "High CPU usage alert policy creation failed or already exists"
    fi
}

# Create storage usage alert
create_storage_usage_alert() {
    local email_channel="$1"
    local slack_channel="$2"
    
    local notification_channels=""
    if [[ -n "$email_channel" ]]; then
        notification_channels="\"$email_channel\""
    fi
    if [[ -n "$slack_channel" ]]; then
        if [[ -n "$notification_channels" ]]; then
            notification_channels="$notification_channels, \"$slack_channel\""
        else
            notification_channels="\"$slack_channel\""
        fi
    fi
    
    local alert_policy=$(cat <<EOF
{
  "displayName": "ImgStream High Storage Usage - ${ENVIRONMENT}",
  "documentation": {
    "content": "This alert fires when GCS bucket usage exceeds 80GB. Review storage usage and implement cleanup policies."
  },
  "conditions": [
    {
      "displayName": "GCS bucket usage above 80GB",
      "conditionThreshold": {
        "filter": "resource.type=\"gcs_bucket\" AND resource.labels.bucket_name=~\".*imgstream.*${ENVIRONMENT}.*\" AND metric.type=\"storage.googleapis.com/storage/total_bytes\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 85899345920,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "3600s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_SUM",
            "groupByFields": ["resource.labels.bucket_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": [$notification_channels]
}
EOF
)
    
    if gcloud alpha monitoring policies create --policy-from-file=<(echo "$alert_policy") > /dev/null 2>&1; then
        log_success "Created storage usage alert policy"
    else
        log_warning "Storage usage alert policy creation failed or already exists"
    fi
}

# Create instance scaling alert
create_instance_scaling_alert() {
    local email_channel="$1"
    local slack_channel="$2"
    
    local notification_channels=""
    if [[ -n "$email_channel" ]]; then
        notification_channels="\"$email_channel\""
    fi
    if [[ -n "$slack_channel" ]]; then
        if [[ -n "$notification_channels" ]]; then
            notification_channels="$notification_channels, \"$slack_channel\""
        else
            notification_channels="\"$slack_channel\""
        fi
    fi
    
    # Adjust threshold based on environment
    local threshold=40
    case $ENVIRONMENT in
        development) threshold=8 ;;  # 80% of 10 max instances
        staging) threshold=16 ;;     # 80% of 20 max instances
        production) threshold=40 ;;  # 80% of 50 max instances
    esac
    
    local alert_policy=$(cat <<EOF
{
  "displayName": "ImgStream Instance Scaling - ${ENVIRONMENT}",
  "documentation": {
    "content": "This alert fires when the number of instances approaches the maximum limit. Review traffic patterns and scaling configuration."
  },
  "conditions": [
    {
      "displayName": "Instance count near maximum",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/container/instance_count\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": $threshold,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_MAX",
            "groupByFields": ["resource.labels.service_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": [$notification_channels]
}
EOF
)
    
    if gcloud alpha monitoring policies create --policy-from-file=<(echo "$alert_policy") > /dev/null 2>&1; then
        log_success "Created instance scaling alert policy"
    else
        log_warning "Instance scaling alert policy creation failed or already exists"
    fi
}

# Create monitoring dashboard
create_dashboard() {
    log_info "Creating monitoring dashboard..."
    
    local dashboard_config=$(cat <<EOF
{
  "displayName": "ImgStream Overview - ${ENVIRONMENT}",
  "mosaicLayout": {
    "tiles": [
      {
        "width": 6,
        "height": 4,
        "widget": {
          "title": "Request Rate",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/request_count\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Requests/sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "widget": {
          "title": "Error Rate",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Errors/sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "yPos": 4,
        "widget": {
          "title": "Response Time (95th percentile)",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/request_latencies\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_DELTA",
                      "crossSeriesReducer": "REDUCE_PERCENTILE_95",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Latency (ms)",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 4,
        "widget": {
          "title": "Memory Utilization",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/container/memory/utilizations\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_MEAN",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Utilization",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "yPos": 8,
        "widget": {
          "title": "CPU Utilization",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/container/cpu/utilizations\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_MEAN",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Utilization",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 8,
        "widget": {
          "title": "Instance Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=~\"imgstream-${ENVIRONMENT}.*\" AND metric.type=\"run.googleapis.com/container/instance_count\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_MAX",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Instances",
              "scale": "LINEAR"
            }
          }
        }
      }
    ]
  }
}
EOF
)
    
    if gcloud monitoring dashboards create --config-from-file=<(echo "$dashboard_config") > /dev/null 2>&1; then
        log_success "Created monitoring dashboard"
    else
        log_warning "Dashboard creation failed or already exists"
    fi
}

# Cleanup temporary files
cleanup() {
    rm -f "/tmp/imgstream-email-channel-${ENVIRONMENT}.txt"
    rm -f "/tmp/imgstream-slack-channel-${ENVIRONMENT}.txt"
}

# Main execution
main() {
    log_info "Setting up Cloud Monitoring for ImgStream"
    log_info "Environment: $ENVIRONMENT"
    log_info "Project: $PROJECT_ID"
    
    validate_prerequisites
    create_notification_channels
    create_alert_policies
    create_dashboard
    cleanup
    
    log_success "Cloud Monitoring setup completed!"
    log_info "You can view your monitoring dashboard in the Google Cloud Console:"
    log_info "https://console.cloud.google.com/monitoring/dashboards"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h          Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  ENVIRONMENT         Target environment (default: production)"
        echo "  GOOGLE_CLOUD_PROJECT GCP project ID (required)"
        echo "  ALERT_EMAIL         Email for notifications (default: ops@example.com)"
        echo "  SLACK_WEBHOOK_URL   Slack webhook URL (optional)"
        exit 0
        ;;
    *)
        main
        ;;
esac
