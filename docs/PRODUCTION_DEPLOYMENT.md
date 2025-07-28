# Production Deployment Guide

This guide covers the complete process for deploying imgstream to production on Google Cloud Platform.

## Prerequisites

Before starting the production deployment, ensure you have:

1. **Google Cloud Project**: A GCP project with billing enabled
2. **Required Permissions**: Owner or Editor role on the GCP project
3. **Tools Installed**:
   - `gcloud` CLI (authenticated)
   - `terraform` (>= 1.0)
   - `docker` (for building images)
   - `git` (for version control)

## Pre-Deployment Checklist

### 1. Environment Setup

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Authenticate with Google Cloud
gcloud auth login
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  iap.googleapis.com
```

### 2. Configuration Review

1. **Update Production Configuration**:
   ```bash
   # Edit the production Terraform variables
   vim terraform/environments/prod.tfvars
   ```

   Key settings to update:
   - `iap_support_email`: Your support email address
   - `allowed_domains`: Your organization's domains (optional)
   - `allowed_users`: Specific user emails (optional)
   - `custom_domain`: Your custom domain (optional)

2. **Review Security Settings**:
   - Ensure `enable_iap = true` for production
   - Verify `enable_security_policy = true`
   - Check `rate_limit_requests_per_minute` is appropriate
   - Review `session_duration` setting

## Deployment Process

### Step 1: Set Up Secrets and Resources

Run the production secrets setup script:

```bash
./scripts/setup-production-secrets.sh -p $PROJECT_ID
```

This script will:
- Enable required APIs
- Create necessary secrets in Secret Manager
- Set up the production GCS bucket
- Configure IAM permissions

### Step 2: Build and Push Docker Image

```bash
# Build the Docker image
docker build -t gcr.io/$PROJECT_ID/imgstream:latest .

# Push to Google Container Registry
docker push gcr.io/$PROJECT_ID/imgstream:latest

# Or use Cloud Build (recommended)
gcloud builds submit --tag gcr.io/$PROJECT_ID/imgstream:latest
```

### Step 3: Deploy Infrastructure and Application

Use the production deployment script:

```bash
# Dry run first to review changes
./scripts/deploy-production.sh -p $PROJECT_ID -i gcr.io/$PROJECT_ID/imgstream:latest --dry-run

# Deploy to production
./scripts/deploy-production.sh -p $PROJECT_ID -i gcr.io/$PROJECT_ID/imgstream:latest
```

Or deploy manually:

```bash
# Deploy infrastructure with Terraform
cd terraform
terraform init
terraform plan -var-file=environments/prod.tfvars -var=project_id=$PROJECT_ID -var=container_image=gcr.io/$PROJECT_ID/imgstream:latest
terraform apply -var-file=environments/prod.tfvars -var=project_id=$PROJECT_ID -var=container_image=gcr.io/$PROJECT_ID/imgstream:latest

# Deploy application to Cloud Run
./scripts/deploy-cloud-run.sh -p $PROJECT_ID -e prod -i gcr.io/$PROJECT_ID/imgstream:latest
```

## Post-Deployment Configuration

### 1. Configure IAP OAuth Consent Screen

1. Go to the [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to "APIs & Services" > "OAuth consent screen"
3. Configure the consent screen:
   - Application name: "imgstream"
   - User support email: Your support email
   - Authorized domains: Add your domain if using custom domain
   - Developer contact information: Your email

### 2. Set Up Custom Domain (Optional)

If you want to use a custom domain:

1. **Configure Domain Mapping**:
   ```bash
   gcloud run domain-mappings create \
     --service imgstream-prod \
     --domain your-domain.com \
     --region us-central1
   ```

2. **Update DNS Records**:
   - Add the CNAME record provided by Cloud Run to your DNS

3. **Update IAP Configuration**:
   - Add your domain to the OAuth consent screen
   - Update the IAP settings to use your custom domain

### 3. Configure Monitoring and Alerting

1. **Set Up Cloud Monitoring**:
   - Create dashboards for Cloud Run metrics
   - Set up alerts for error rates and response times

2. **Configure Log-based Metrics**:
   ```bash
   # Create log-based metrics for application errors
   gcloud logging metrics create error_rate \
     --description="Application error rate" \
     --log-filter='resource.type="cloud_run_revision" AND severity>=ERROR'
   ```

### 4. Verify Deployment

1. **Health Check**:
   ```bash
   # Get the service URL
   SERVICE_URL=$(gcloud run services describe imgstream-prod \
     --region=us-central1 \
     --format='value(status.url)')
   
   # Check health endpoint (will redirect to IAP login)
   curl -I $SERVICE_URL
   ```

2. **Access the Application**:
   - Navigate to your service URL
   - Complete IAP authentication
   - Verify all functionality works

## Security Considerations

### 1. IAP Configuration

- **Enable IAP**: Ensures all access goes through Google's authentication
- **Configure Allowed Users/Domains**: Restrict access to authorized users
- **Session Duration**: Set appropriate session timeout (default: 1 hour)

### 2. Cloud Armor Security Policy

The deployment includes:
- Rate limiting (100 requests/minute per IP)
- Geographic restrictions (if configured)
- WAF rules for common attacks

### 3. Secret Management

- All sensitive data stored in Secret Manager
- Secrets are automatically rotated
- Access is logged and monitored

### 4. Network Security

- Cloud Run service is not publicly accessible (IAP required)
- All traffic is encrypted in transit (HTTPS)
- Internal communication uses Google's private network

## Monitoring and Maintenance

### 1. Health Monitoring

The application provides several health check endpoints:

- `/health`: Comprehensive health check
- `/health?endpoint=readiness`: Readiness probe
- `/health?endpoint=liveness`: Liveness probe
- `/health?format=json`: JSON format health data

### 2. Log Monitoring

Monitor these log patterns:
- Error logs: `severity>=ERROR`
- Authentication failures: `security_event`
- Performance issues: `duration_ms>5000`

### 3. Resource Monitoring

Key metrics to monitor:
- **Request Count**: Number of requests per minute
- **Request Latency**: 95th percentile response time
- **Error Rate**: Percentage of 4xx/5xx responses
- **Memory Usage**: Container memory utilization
- **CPU Usage**: Container CPU utilization

### 4. Regular Maintenance

- **Update Dependencies**: Regularly update Python packages
- **Rotate Secrets**: Rotate secrets every 90 days
- **Review Access**: Audit IAP access logs monthly
- **Update Images**: Deploy security updates promptly

## Troubleshooting

### Common Issues

1. **IAP Authentication Errors**:
   - Verify OAuth consent screen configuration
   - Check allowed users/domains settings
   - Ensure IAP is enabled for the service

2. **Storage Access Errors**:
   - Verify GCS bucket exists and is accessible
   - Check service account permissions
   - Ensure bucket name is correctly configured

3. **Secret Access Errors**:
   - Verify secrets exist in Secret Manager
   - Check IAM permissions for service account
   - Ensure secret names match configuration

4. **Performance Issues**:
   - Check Cloud Run instance limits
   - Monitor memory and CPU usage
   - Review database query performance

### Getting Help

1. **Check Logs**:
   ```bash
   gcloud logs read "resource.type=cloud_run_revision" \
     --project=$PROJECT_ID \
     --limit=50
   ```

2. **Check Service Status**:
   ```bash
   gcloud run services describe imgstream-prod \
     --region=us-central1 \
     --project=$PROJECT_ID
   ```

3. **Health Check**:
   ```bash
   curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     "$SERVICE_URL/health?format=json"
   ```

## Rollback Procedure

If you need to rollback a deployment:

1. **Identify Previous Revision**:
   ```bash
   gcloud run revisions list \
     --service=imgstream-prod \
     --region=us-central1 \
     --limit=5
   ```

2. **Rollback to Previous Revision**:
   ```bash
   gcloud run services update-traffic imgstream-prod \
     --to-revisions=REVISION_NAME=100 \
     --region=us-central1
   ```

3. **Verify Rollback**:
   ```bash
   # Check service status
   gcloud run services describe imgstream-prod \
     --region=us-central1
   
   # Test health endpoint
   curl -I $SERVICE_URL
   ```

## Cost Optimization

### 1. Cloud Run Configuration

- **Min Instances**: Set to 1 for production (avoid cold starts)
- **Max Instances**: Set to 10 (adjust based on expected load)
- **CPU/Memory**: Start with 1 CPU, 2Gi memory (monitor and adjust)

### 2. Storage Optimization

- **Lifecycle Policies**: Automatically move old files to cheaper storage
- **Compression**: Enable compression for stored images
- **Cleanup**: Regularly clean up unused files

### 3. Monitoring Costs

- Set up billing alerts
- Monitor resource usage regularly
- Review and optimize based on actual usage patterns

## Compliance and Auditing

### 1. Access Logging

- All access is logged through IAP
- Cloud Run request logs are available
- Secret Manager access is logged

### 2. Data Protection

- All data is encrypted at rest and in transit
- User data is isolated by user ID
- Regular backups are maintained

### 3. Audit Trail

- All infrastructure changes are tracked through Terraform
- Application deployments are logged
- Configuration changes are version controlled

---

For additional support or questions, please refer to the project documentation or contact the development team.
