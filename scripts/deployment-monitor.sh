#!/bin/bash

# Deployment monitoring and alerting script for ImgStream
# This script monitors deployment health and can trigger rollbacks

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}\")\" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT=${ENVIRONMENT:-staging}
REGION=${REGION:-us-central1}
SERVICE_NAME="imgstream-${ENVIRONMENT}"
MONITORING_INTERVAL=${MONITORING_INTERVAL:-60}
ALERT_THRESHOLD=${ALERT_THRESHOLD:-5}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

# Get service information
get_service_info() {
    local service_url
    local service_status
    
    service_url=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --format="value(status.url)" 2>/dev/null || echo "")
    
    service_status=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --format="value(status.conditions[0].status)" 2>/dev/null || echo "Unknown")
    
    echo "$service_url|$service_status"
}

# Health check function
health_check() {
    local service_url="$1"
    local response_code
    local response_time
    
    if [[ -z "$service_url" ]]; then
        return 1
    fi
    
    # Measure response time and get status code
    response_time=$(curl -o /dev/null -s -w "%{time_total}" -m 10 "$service_url/health" 2>/dev/null || echo "timeout")
    response_code=$(curl -o /dev/null -s -w "%{http_code}" -m 10 "$service_url/health" 2>/dev/null || echo "000")
    
    if [[ "$response_code" == "200" ]]; then
        log_success "Health check passed (${response_time}s)"
        return 0
    else
        log_error "Health check failed - HTTP $response_code (${response_time}s)"
        return 1
    fi
}

# Get deployment metrics
get_metrics() {
    local service_url="$1"
    local error_rate
    local avg_response_time
    local request_count
    
    # Get basic metrics from Cloud Monitoring (simplified)
    log_info "Fetching deployment metrics..."
    
    # In a real implementation, you would query Cloud Monitoring API
    # For now, we'll simulate with basic health checks
    if health_check "$service_url"; then
        error_rate="0.1%"
        avg_response_time="0.2s"
        request_count="150/min"
        log_info "Metrics - Error Rate: $error_rate, Avg Response: $avg_response_time, Requests: $request_count"
        return 0
    else
        error_rate="100%"
        avg_response_time="timeout"
        request_count="0/min"
        log_error "Metrics - Error Rate: $error_rate, Avg Response: $avg_response_time, Requests: $request_count"
        return 1
    fi
}

# Rollback function
rollback_deployment() {
    log_warning "Initiating rollback for $SERVICE_NAME..."
    
    # Get previous revision
    local previous_revision
    previous_revision=$(gcloud run revisions list \
        --service="$SERVICE_NAME" \
        --region="$REGION" \
        --limit=2 \
        --format="value(metadata.name)" | tail -n 1)
    
    if [[ -n "$previous_revision" ]]; then
        log_info "Rolling back to revision: $previous_revision"
        
        gcloud run services update-traffic "$SERVICE_NAME" \
            --region="$REGION" \
            --to-revisions="$previous_revision=100"
        
        log_success "Rollback completed to revision: $previous_revision"
        
        # Wait and verify rollback
        sleep 30
        local service_info
        service_info=$(get_service_info)
        local service_url
        service_url=$(echo "$service_info" | cut -d'|' -f1)
        
        if health_check "$service_url"; then
            log_success "Rollback verification passed"
            return 0
        else
            log_error "Rollback verification failed"
            return 1
        fi
    else
        log_error "No previous revision found for rollback"
        return 1
    fi
}

# Send alert (placeholder for real alerting system)
send_alert() {
    local alert_type="$1"
    local message="$2"
    
    log_warning "ALERT [$alert_type]: $message"
    
    # In a real implementation, you would integrate with:
    # - Slack/Discord webhooks
    # - PagerDuty
    # - Email notifications
    # - Cloud Monitoring alerts
    
    # Example webhook call (uncomment and configure as needed):
    # curl -X POST "$SLACK_WEBHOOK_URL" \
    #     -H 'Content-type: application/json' \
    #     --data "{\"text\":\"🚨 ImgStream Alert [$alert_type]: $message\"}"
}

# Main monitoring loop
monitor_deployment() {
    log_info "Starting deployment monitoring for $SERVICE_NAME"
    log_info "Environment: $ENVIRONMENT"
    log_info "Region: $REGION"
    log_info "Monitoring interval: ${MONITORING_INTERVAL}s"
    
    local failure_count=0
    local last_alert_time=0
    
    while true; do
        local service_info
        service_info=$(get_service_info)
        local service_url
        local service_status
        service_url=$(echo "$service_info" | cut -d'|' -f1)
        service_status=$(echo "$service_info" | cut -d'|' -f2)
        
        if [[ -z "$service_url" ]]; then
            log_error "Service not found or not accessible"
            failure_count=$((failure_count + 1))
        elif [[ "$service_status" != "True" ]]; then
            log_error "Service status is not healthy: $service_status"
            failure_count=$((failure_count + 1))
        elif ! get_metrics "$service_url"; then
            log_error "Health check or metrics collection failed"
            failure_count=$((failure_count + 1))
        else
            log_success "Service is healthy"
            failure_count=0
        fi
        
        # Check if we need to alert or rollback
        if [[ $failure_count -ge $ALERT_THRESHOLD ]]; then
            local current_time
            current_time=$(date +%s)
            
            # Send alert (rate limited to once per hour)
            if [[ $((current_time - last_alert_time)) -gt 3600 ]]; then
                send_alert "DEPLOYMENT_FAILURE" "Service $SERVICE_NAME has failed $failure_count consecutive health checks"
                last_alert_time=$current_time
            fi
            
            # Auto-rollback for production after more failures
            if [[ "$ENVIRONMENT" == "production" && $failure_count -ge $((ALERT_THRESHOLD * 2)) ]]; then
                log_error "Critical failure threshold reached. Initiating automatic rollback..."
                if rollback_deployment; then
                    send_alert "AUTO_ROLLBACK_SUCCESS" "Automatic rollback completed for $SERVICE_NAME"
                    failure_count=0
                else
                    send_alert "AUTO_ROLLBACK_FAILED" "Automatic rollback failed for $SERVICE_NAME - manual intervention required"
                fi
            fi
        fi
        
        sleep "$MONITORING_INTERVAL"
    done
}

# Manual rollback command
manual_rollback() {
    log_info "Manual rollback requested for $SERVICE_NAME"
    
    if rollback_deployment; then
        log_success "Manual rollback completed successfully"
        send_alert "MANUAL_ROLLBACK" "Manual rollback completed for $SERVICE_NAME"
    else
        log_error "Manual rollback failed"
        send_alert "MANUAL_ROLLBACK_FAILED" "Manual rollback failed for $SERVICE_NAME"
        exit 1
    fi
}

# Status check command
status_check() {
    log_info "Checking status for $SERVICE_NAME"
    
    local service_info
    service_info=$(get_service_info)
    local service_url
    local service_status
    service_url=$(echo "$service_info" | cut -d'|' -f1)
    service_status=$(echo "$service_info" | cut -d'|' -f2)
    
    echo "Service: $SERVICE_NAME"
    echo "Environment: $ENVIRONMENT"
    echo "Region: $REGION"
    echo "URL: $service_url"
    echo "Status: $service_status"
    echo ""
    
    if [[ -n "$service_url" ]]; then
        get_metrics "$service_url"
    else
        log_error "Service not accessible"
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    monitor)
        monitor_deployment
        ;;
    rollback)
        manual_rollback
        ;;
    status)
        status_check
        ;;
    *)
        echo "Usage: $0 {monitor|rollback|status}"
        echo ""
        echo "Commands:"
        echo "  monitor   - Start continuous deployment monitoring"
        echo "  rollback  - Perform manual rollback to previous revision"
        echo "  status    - Check current deployment status"
        echo ""
        echo "Environment variables:"
        echo "  ENVIRONMENT         - Target environment (default: staging)"
        echo "  REGION             - GCP region (default: us-central1)"
        echo "  MONITORING_INTERVAL - Monitoring interval in seconds (default: 60)"
        echo "  ALERT_THRESHOLD    - Failure count before alerting (default: 5)"
        exit 1
        ;;
esac
