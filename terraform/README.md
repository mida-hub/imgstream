# ImgStream Terraform Infrastructure

This directory contains the Terraform configuration for the ImgStream photo management application infrastructure on Google Cloud Platform.

## Directory Structure

```
terraform/
├── common/                 # Shared resources (GitHub OIDC) - Deploy once
│   ├── main.tf
│   ├── github-oidc.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars
├── modules/
│   └── imgstream/         # ImgStream application module
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── storage.tf
│       ├── cloud_run.tf
│       ├── artifact_registry.tf
│       ├── iap.tf
│       ├── security.tf
│       └── monitoring.tf
├── dev/                   # Development environment
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── dev.tfvars
├── prod/                  # Production environment
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── prod.tfvars
# Backend configurations are now embedded in main.tf files
└── README.md
```

## Architecture Overview

### Common Resources
- **GitHub OIDC**: Workload Identity Pool and Provider for GitHub Actions authentication
- **Service Account**: GitHub Actions service account with necessary permissions

### ImgStream Module
- **Cloud Run**: Containerized application deployment
- **Cloud Storage**: Photo storage and database backup buckets
- **Artifact Registry**: Container image repository
- **IAP (Identity-Aware Proxy)**: Authentication and authorization
- **Cloud Armor**: Security policies and WAF rules
- **Monitoring**: Alerts, dashboards, and notification channels

## Usage

### Prerequisites

1. Install Terraform >= 1.12
2. Install Google Cloud SDK
3. Authenticate with Google Cloud:
   ```bash
   gcloud auth application-default login
   ```
4. Ensure the GCS bucket `apps-466614-terraform-state` exists for state storage

### Deployment Order

**IMPORTANT**: Deploy in this order to avoid dependency issues.

#### 1. Common Infrastructure (Deploy Once)

Deploy the shared GitHub OIDC resources first:

```bash
cd terraform/common
terraform init
terraform plan
terraform apply
```

#### 2. Development Environment

```bash
cd terraform/dev
terraform init
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

#### 3. Production Environment

```bash
cd terraform/prod
terraform init
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

## Configuration

### Sensitive Information Management

**IMPORTANT**: This repository is public, so personal information (email addresses, etc.) should not be committed to version control.

#### Option 1: Environment Variables (Recommended)
Set sensitive values using environment variables:

```bash
# Set environment variables
export TF_VAR_allowed_users='["user1@example.com","user2@example.com"]'
export TF_VAR_iap_support_email="support@example.com"
export TF_VAR_alert_email="alerts@example.com"

# Then run terraform
terraform apply -var-file=dev.tfvars
```

#### Option 2: Local Configuration Files
Create local configuration files that are not committed to git:

```bash
# Copy the example file
cp terraform.tfvars.local.example terraform.tfvars.local

# Edit with your actual values
vim terraform.tfvars.local

# The deploy script will automatically include this file
```

### Environment Variables

Each environment has its own `.tfvars` file with environment-specific configurations:

- **dev.tfvars**: Development environment settings
  - Public access enabled
  - IAP disabled
  - Minimal instances for cost savings
  - Relaxed security policies

- **prod.tfvars**: Production environment settings
  - IAP enabled for security
  - Minimum instances for availability
  - Full security policies enabled
  - Production-grade monitoring

### Key Configuration Options

| Variable | Description | Dev Default | Prod Default |
|----------|-------------|-------------|--------------|
| `enable_public_access` | Allow public access | `true` | `false` |
| `enable_iap` | Enable Identity-Aware Proxy | `false` | `true` |
| `min_instances` | Minimum Cloud Run instances | `0` | `1` |
| `max_instances` | Maximum Cloud Run instances | `3` | `10` |
| `enable_security_policy` | Enable Cloud Armor | `false` | `true` |
| `enable_waf_rules` | Enable WAF rules | `false` | `true` |

## Outputs

After successful deployment, Terraform will output important information:

- **cloud_run_service_url**: URL of the deployed application
- **artifact_registry_repository_url**: Container registry URL
- **photos_bucket_name**: GCS bucket for photo storage
- **workload_identity_provider**: GitHub Actions OIDC provider
- **monitoring_dashboard_url**: Link to monitoring dashboard

## Security Features

### Identity-Aware Proxy (IAP)
- OAuth-based authentication
- User and domain-based access control
- Session management

### Cloud Armor Security Policies
- Rate limiting
- Geographic restrictions
- XSS and SQL injection protection
- Custom security rules

### Storage Security
- Uniform bucket-level access
- Service account-based permissions
- Lifecycle management
- Versioning for database backups

## Monitoring and Alerting

### Alert Policies
- Service availability monitoring
- High error rate detection
- Response time monitoring
- Resource utilization alerts
- Storage usage monitoring

### Notification Channels
- Email notifications
- Slack integration (optional)
- Custom webhook support

### Dashboards
- Real-time metrics visualization
- Request rate and error tracking
- Resource utilization monitoring
- Storage usage analytics

## Maintenance

### Updating Infrastructure

1. Modify the appropriate `.tfvars` file
2. Run `terraform plan` to review changes
3. Run `terraform apply` to apply changes

### Adding New Environments

1. Create a new directory (e.g., `staging/`)
2. Copy files from `dev/` or `prod/`
3. Create environment-specific `.tfvars` file
4. Create backend configuration file
5. Initialize and apply

### Module Updates

The ImgStream module is versioned and can be updated independently. When updating:

1. Review module changes
2. Test in development environment first
3. Apply to production after validation

## Troubleshooting

### Common Issues

1. **Backend initialization fails**
   - Ensure GCS bucket `apps-466614-terraform-state` exists
   - Check permissions on the bucket
   - Verify you have deployed common infrastructure first

2. **Remote state data source fails**
   - Ensure common infrastructure has been deployed first
   - Check that common state exists in GCS bucket

3. **IAP setup fails**
   - Verify OAuth consent screen is configured
   - Check domain verification

4. **Cloud Run deployment fails**
   - Verify container image exists in Artifact Registry
   - Check service account permissions

### Getting Help

- Check Terraform logs: `terraform apply -debug`
- Review Google Cloud Console for resource status
- Validate configuration: `terraform validate`
- Format code: `terraform fmt -recursive`

## Best Practices

1. **State Management**
   - Use remote state storage (GCS)
   - Enable state locking
   - Regular state backups

2. **Security**
   - Use least-privilege service accounts
   - Enable audit logging
   - Regular security reviews

3. **Cost Optimization**
   - Use appropriate instance sizing
   - Implement lifecycle policies
   - Monitor resource usage

4. **Deployment**
   - Test in development first
   - Use infrastructure as code
   - Implement proper CI/CD pipelines
