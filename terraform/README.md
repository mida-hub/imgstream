# Imgstream Infrastructure

This directory contains Terraform configurations for deploying the imgstream photo management application infrastructure on Google Cloud Platform.

## Prerequisites

1. **Google Cloud SDK**: Install and configure the gcloud CLI
   ```bash
   # Install gcloud CLI (macOS)
   brew install google-cloud-sdk
   
   # Authenticate
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Terraform**: Install Terraform (version >= 1.0)
   ```bash
   # Install Terraform (macOS)
   brew install terraform
   ```

3. **GCP Project**: Create a GCP project and enable billing

## Quick Start

1. **Clone and navigate to terraform directory**
   ```bash
   cd terraform
   ```

2. **Copy and configure variables**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your project-specific values
   ```

3. **Deploy infrastructure**
   ```bash
   # Make deploy script executable
   chmod +x scripts/deploy.sh
   
   # Plan deployment (recommended first step)
   ./scripts/deploy.sh -p YOUR_PROJECT_ID -e dev -a plan
   
   # Apply deployment
   ./scripts/deploy.sh -p YOUR_PROJECT_ID -e dev -a apply
   ```

## Infrastructure Components

### Storage Buckets

1. **Photos Bucket** (`imgstream-photos-{env}-{suffix}`)
   - Stores original photos and thumbnails
   - Lifecycle policy: Standard → Coldline (30 days) → Archive (365 days)
   - Public read access for signed URLs
   - CORS enabled for web access

2. **Database Bucket** (`imgstream-database-{env}-{suffix}`)
   - Stores DuckDB backup files
   - Versioning enabled
   - Lifecycle policy: Standard → Coldline (7 days) → Archive (90 days) → Delete (365 days)
   - Private access only

### Service Accounts

1. **Cloud Run Service Account**
   - Used by the application for GCS access
   - Permissions: Storage Object Admin, Logging, Monitoring

2. **Monitoring Service Account**
   - Used for monitoring and alerting
   - Permissions: Monitoring Viewer, Logging Viewer, Storage Object Viewer

### Security Features

- Uniform bucket-level access enabled
- Principle of least privilege for service accounts
- Required APIs automatically enabled
- Bucket-level IAM bindings for access control

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `project_id` | GCP project ID | - | Yes |
| `region` | GCP region | `us-central1` | No |
| `environment` | Environment name | `dev` | No |
| `bucket_location` | GCS bucket location | `US` | No |
| `lifecycle_coldline_days` | Days to Coldline transition | `30` | No |
| `lifecycle_archive_days` | Days to Archive transition | `365` | No |
| `lifecycle_delete_days` | Days to deletion (0=never) | `0` | No |

### Environment-Specific Configurations

- **Development** (`environments/dev.tfvars`)
  - Shorter lifecycle policies for cost optimization
  - Auto-deletion after 90 days
  - Relaxed security settings

- **Production** (`environments/prod.tfvars`)
  - Standard lifecycle policies
  - No auto-deletion
  - Strict security settings

## Deployment Commands

### Using the Deploy Script

```bash
# Plan deployment
./scripts/deploy.sh -p PROJECT_ID -e ENVIRONMENT -a plan

# Apply deployment
./scripts/deploy.sh -p PROJECT_ID -e ENVIRONMENT -a apply

# Apply with auto-approval
./scripts/deploy.sh -p PROJECT_ID -e ENVIRONMENT -a apply --auto-approve

# Destroy infrastructure
./scripts/deploy.sh -p PROJECT_ID -e ENVIRONMENT -a destroy
```

### Manual Terraform Commands

```bash
# Initialize
terraform init

# Plan
terraform plan -var-file="environments/dev.tfvars" -var="project_id=YOUR_PROJECT_ID"

# Apply
terraform apply -var-file="environments/dev.tfvars" -var="project_id=YOUR_PROJECT_ID"

# Destroy
terraform destroy -var-file="environments/dev.tfvars" -var="project_id=YOUR_PROJECT_ID"
```

## Outputs

After successful deployment, Terraform will output:

- `photos_bucket_name`: Name of the photos storage bucket
- `photos_bucket_url`: URL of the photos storage bucket
- `database_bucket_name`: Name of the database backup bucket
- `database_bucket_url`: URL of the database backup bucket
- `service_account_email`: Email of the Cloud Run service account

## Cost Optimization

### Free Tier Considerations

- **GCS Storage**: 5GB free per month
- **GCS Operations**: 5,000 Class A operations, 50,000 Class B operations per month
- **Lifecycle policies**: Automatically move data to cheaper storage classes

### Lifecycle Policies

1. **Photos Bucket**:
   - Standard storage for first 30 days (frequent access)
   - Coldline storage after 30 days (monthly access)
   - Archive storage after 365 days (yearly access)
   - Optional deletion (disabled by default)

2. **Database Bucket**:
   - Standard storage for first 7 days
   - Coldline storage after 7 days
   - Archive storage after 90 days
   - Automatic deletion after 365 days

## Security Best Practices

1. **Bucket Access**:
   - Uniform bucket-level access enabled
   - Service account-based access only
   - No public write access

2. **Service Accounts**:
   - Principle of least privilege
   - Separate accounts for different purposes
   - Regular key rotation (handled by GCP)

3. **Monitoring**:
   - Cloud Logging integration
   - Cloud Monitoring integration
   - Audit logs enabled

## Troubleshooting

### Common Issues

1. **Permission Denied**:
   ```bash
   # Ensure you're authenticated
   gcloud auth login
   gcloud auth application-default login
   
   # Check project permissions
   gcloud projects get-iam-policy PROJECT_ID
   ```

2. **Bucket Name Conflicts**:
   - Bucket names are globally unique
   - The configuration uses random suffixes to avoid conflicts
   - If conflicts occur, run `terraform apply` again

3. **API Not Enabled**:
   ```bash
   # Enable required APIs manually
   gcloud services enable storage.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable iap.googleapis.com
   ```

### State Management

- Terraform state is stored locally by default
- For production, consider using remote state storage:
  ```hcl
  terraform {
    backend "gcs" {
      bucket = "your-terraform-state-bucket"
      prefix = "imgstream/terraform.tfstate"
    }
  }
  ```

## Next Steps

After deploying the storage infrastructure:

1. Deploy Cloud Run service (Task 11.2)
2. Configure Cloud IAP (Task 11.3)
3. Set up CI/CD pipeline (Task 12)
4. Configure monitoring and alerting (Task 14.2)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Terraform and GCP documentation
3. Check application logs in Cloud Logging
