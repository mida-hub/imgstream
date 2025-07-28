# Deployment Automation Guide

This comprehensive guide covers the deployment automation system for the ImgStream photo management application, including CI/CD pipelines, environment management, monitoring, and rollback procedures.

## Overview

The deployment automation system provides:
- **Multi-environment support** (development, staging, production)
- **Automated CI/CD pipelines** with GitHub Actions and Cloud Build
- **Environment-specific configurations** with validation
- **Automated testing** (unit, integration, security)
- **Deployment monitoring** and health checks
- **Automatic rollback** capabilities
- **Security scanning** and compliance checks

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Development   │    │     Staging      │    │   Production    │
│                 │    │                  │    │                 │
│ • Auto-deploy   │    │ • Auto-deploy    │    │ • Manual deploy │
│ • Basic tests   │    │ • Full tests     │    │ • Full tests    │
│ • Local storage │    │ • GCS storage    │    │ • GCS storage   │
│ • Debug mode    │    │ • Monitoring     │    │ • IAP auth      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Prerequisites

### Required Tools
- Google Cloud Platform account with billing enabled
- Docker installed locally
- Google Cloud SDK (gcloud) installed and configured
- Python 3.11+ with uv package manager
- Appropriate IAM permissions

### Required APIs
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com
```

## Environment Configuration

### Configuration Files
Environment-specific configurations are stored in `config/environments/`:
- `development.yaml` - Local development settings
- `staging.yaml` - Staging environment settings  
- `production.yaml` - Production environment settings

### Configuration Management
The application uses a centralized configuration system (`src/imgstream/config.py`) that:
- Loads environment-specific YAML configurations
- Expands environment variables
- Validates configuration completeness
- Provides type-safe configuration access

### Environment Variables

#### Required for All Environments
```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export ENVIRONMENT="staging"  # or development, production
```

#### Staging Environment
```bash
export GCS_BUCKET_STAGING="your-staging-bucket"
export IAP_AUDIENCE="staging-iap-audience"
```

#### Production Environment
```bash
export GCS_BUCKET_PRODUCTION="your-production-bucket"
export IAP_AUDIENCE="production-iap-audience"
```

## GitHub Secrets Setup

To run deployment workflows, configure the following secrets in your GitHub repository.

### Required Secrets

| Secret Name | Description | Example |
|---|---|---|
| `GCP_SA_KEY` | GCP Service Account Key (JSON format) | `{"type": "service_account", ...}` |
| `GCP_PROJECT_ID` | GCP Project ID | `my-imgstream-project` |
| `GCS_BUCKET_DEV` | Development GCS bucket name | `my-project-imgstream-dev` |
| `GCS_BUCKET_PROD` | Production GCS bucket name | `my-project-imgstream-prod` |

### Optional Secrets

| Secret Name | Description | Example |
|---|---|---|
| `PROD_DOMAIN_URL` | Production custom domain URL | `https://imgstream.example.com` |
| `SONAR_TOKEN` | SonarCloud token | `sqp_...` |

### Service Account Creation and Setup

1. **Create Service Account**
   ```bash
   gcloud iam service-accounts create imgstream-deploy \
     --display-name="ImgStream Deployment Service Account" \
     --project=YOUR_PROJECT_ID
   ```

2. **Grant Required Permissions**
   ```bash
   # Cloud Run Admin
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.admin"
   
   # Storage Admin
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   
   # Container Registry Admin
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   
   # IAM Service Account User
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"
   ```

3. **Create Service Account Key**
   ```bash
   gcloud iam service-accounts keys create key.json \
     --iam-account=imgstream-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

4. **Configure GitHub Secrets**
   - Go to GitHub repository Settings > Secrets and variables > Actions
   - Add `GCP_SA_KEY` with the contents of `key.json`

## Deployment Methods

### 1. GitHub Actions (Recommended)

#### Workflow Features
- **Multi-environment support** with manual and automatic triggers
- **Comprehensive testing** (unit, integration, security, code quality)
- **Docker image building** with metadata and caching
- **Security scanning** with Trivy
- **Environment-specific deployments** with approval gates
- **Health checks** and smoke tests
- **Automatic rollback** on failure

#### Setup
1. Add repository secrets (see GitHub Secrets Setup section)

2. Deployment triggers:
   - **Staging**: Push to `develop` branch
   - **Production**: Push to `main` branch or manual trigger
   - **Manual**: Use workflow_dispatch with environment selection

### 2. Cloud Build

#### Enhanced Cloud Build Features
- **Environment-specific builds** with substitution variables
- **Automated testing** before deployment
- **Code quality checks** (black, ruff, mypy)
- **Security scanning** of container images
- **Health verification** after deployment
- **Image cleanup** to manage storage costs

#### Usage
```bash
# Deploy to staging
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _ENVIRONMENT=staging

# Deploy to production
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _ENVIRONMENT=production,_VERSION=v1.0.0
```

#### Trigger Configuration
Use the provided trigger configurations:
- `config/cloudbuild/staging.yaml` - Staging triggers
- `config/cloudbuild/production.yaml` - Production triggers

### 3. Manual Deployment

#### Enhanced Deployment Script
The `scripts/deploy-cloud-run.sh` script provides:
- **Environment validation** and prerequisite checks
- **Comprehensive testing** before deployment
- **Docker image building** with metadata
- **Environment-specific configuration**
- **Health checks** and verification
- **Rollback capabilities**

#### Usage
```bash
# Validate configuration first
./scripts/validate-deployment-config.sh staging

# Deploy to staging
ENVIRONMENT=staging ./scripts/deploy-cloud-run.sh

# Deploy to production
ENVIRONMENT=production ./scripts/deploy-cloud-run.sh

# Rollback if needed
ENVIRONMENT=production ./scripts/deploy-cloud-run.sh rollback
```

## Configuration Validation

### Validation Script
Use `scripts/validate-deployment-config.sh` to verify:
- Configuration file syntax and completeness
- Required environment variables
- Google Cloud authentication and APIs
- Docker configuration
- IAM service accounts
- Storage bucket accessibility
- Deployment file presence

### Usage
```bash
# Validate staging environment
./scripts/validate-deployment-config.sh staging

# Validate production environment
ENVIRONMENT=production ./scripts/validate-deployment-config.sh
```

## Monitoring and Alerting

### Deployment Monitor
The `scripts/deployment-monitor.sh` provides:
- **Continuous health monitoring**
- **Metrics collection** and analysis
- **Automatic alerting** on failures
- **Auto-rollback** for critical failures
- **Manual rollback** capabilities

### Usage
```bash
# Start monitoring
ENVIRONMENT=production ./scripts/deployment-monitor.sh monitor

# Check status
./scripts/deployment-monitor.sh status

# Manual rollback
./scripts/deployment-monitor.sh rollback
```

### Health Endpoints
- `/health` - Comprehensive health check with dependencies
- `/_stcore/health` - Basic application health

### Monitoring Integration
- **Cloud Monitoring** - Automatic metrics and alerting
- **Error Reporting** - Centralized error tracking
- **Cloud Logging** - Structured logging with correlation
- **Custom alerts** - Configurable thresholds and notifications

## Environment-Specific Configuration

### Development Environment
- **Authentication**: Public access (no authentication)
- **Scaling**: 0-10 instances
- **Resources**: 512Mi memory, 1 CPU
- **Storage**: Local file storage option
- **Logging**: Debug level
- **URL**: Cloud Run auto-generated URL

### Staging Environment
- **Authentication**: Optional IAP
- **Scaling**: 1-20 instances
- **Resources**: 1Gi memory, 1 CPU
- **Storage**: GCS bucket required
- **Logging**: Info level
- **URL**: Staging subdomain

### Production Environment
- **Authentication**: Cloud IAP (authentication required)
- **Scaling**: 2-50 instances
- **Resources**: 2Gi memory, 2 CPU
- **Storage**: GCS bucket with redundancy
- **Logging**: Warning level
- **URL**: Custom domain (if configured)

## Troubleshooting

### Common Issues

1. **Deployment Failures**
   - Verify GitHub Secrets are correctly configured
   - Check service account permissions
   - Ensure Cloud Run API is enabled

2. **Health Check Failures**
   - Verify environment variables are set correctly
   - Check GCS bucket exists and is accessible
   - Verify service account permissions

3. **Application Access Issues**
   - Check Cloud IAP settings (production)
   - Verify DNS configuration (custom domain)
   - Check SSL certificate status

### Debugging Tools
- **Structured logging** with correlation IDs
- **Health check endpoints** for diagnostics
- **Metrics dashboards** in Cloud Console
- **Error reporting** with stack traces

### Logs and Debugging

```bash
# View application logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=imgstream-prod" --limit=50

# View build logs
gcloud builds log [BUILD_ID]

# Check service status
gcloud run services describe imgstream-prod --region=us-central1
```

## Rollback Procedures

### Automatic Rollback
- **Health check failures** trigger automatic rollback
- **Configurable thresholds** for failure detection
- **Previous revision** restoration
- **Notification system** for rollback events

### Manual Rollback
```bash
# Using deployment monitor
./scripts/deployment-monitor.sh rollback

# Using deployment script
ENVIRONMENT=production ./scripts/deploy-cloud-run.sh rollback

# Using gcloud directly
gcloud run services update-traffic imgstream-production \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1
```

## Security

### Container Security
- **Base image scanning** with Trivy
- **Vulnerability assessment** in CI/CD
- **Security test suite** for authentication and authorization
- **Minimal container images** with distroless base

### Authentication & Authorization
- **IAP (Identity-Aware Proxy)** for production
- **Service account** with minimal permissions
- **JWT token validation** for API access
- **CORS configuration** per environment

### Secrets Management
- **Google Secret Manager** integration
- **Environment variable** expansion
- **No secrets in code** or configuration files
- **Service account key** rotation

## Performance Optimization

### Environment-Specific Scaling
```yaml
Development:
  CPU: 1 core
  Memory: 512Mi
  Min instances: 0
  Max instances: 10
  Concurrency: 80

Staging:
  CPU: 1 core  
  Memory: 1Gi
  Min instances: 1
  Max instances: 20
  Concurrency: 100

Production:
  CPU: 2 cores
  Memory: 2Gi
  Min instances: 2
  Max instances: 50
  Concurrency: 100
```

### Optimization Features
- **Container image caching** for faster builds
- **Multi-stage builds** for smaller images
- **Resource right-sizing** per environment
- **Auto-scaling** based on demand
- **Connection pooling** and caching

## Cost Optimization

### Resource Management
- **Right-sized instances** per environment
- **Auto-scaling** to minimize idle resources
- **Container image cleanup** to reduce storage costs
- **Efficient caching** strategies

### Monitoring Costs
- **Billing alerts** for unexpected usage
- **Resource utilization** monitoring
- **Cost attribution** by environment
- **Regular cost reviews** and optimization

## Maintenance

### Regular Tasks
1. **Dependency updates** - Monthly security patches
2. **Configuration reviews** - Quarterly settings audit
3. **Service account rotation** - Bi-annual key rotation
4. **Performance tuning** - Ongoing optimization
5. **Documentation updates** - As needed

### Backup and Recovery
- **Configuration backup** in version control
- **Database backups** automated
- **GCS redundancy** built-in
- **Disaster recovery** procedures documented

## Best Practices

### Development Workflow
1. **Feature branches** with pull requests
2. **Automated testing** on all changes
3. **Code review** requirements
4. **Staging deployment** before production
5. **Monitoring** after deployment

### Security Practices
1. **Principle of least privilege** for service accounts
2. **Regular security scans** in CI/CD
3. **Secrets rotation** schedule
4. **Vulnerability monitoring** and patching
5. **Compliance auditing** regular reviews

### Operational Excellence
1. **Infrastructure as Code** for all resources
2. **Automated testing** at all levels
3. **Comprehensive monitoring** and alerting
4. **Incident response** procedures
5. **Continuous improvement** culture

## Reference Links

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Cloud IAP Documentation](https://cloud.google.com/iap/docs)
- [Google Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Container Security Best Practices](https://cloud.google.com/architecture/best-practices-for-operating-containers)
