# Deployment Scripts

This directory contains scripts for deploying imgstream to various environments.

## Scripts Overview

### Production Deployment

- **`deploy-production.sh`**: Complete production deployment script
- **`setup-production-secrets.sh`**: Set up secrets and resources for production
- **`deploy-cloud-run.sh`**: Deploy application to Cloud Run (any environment)

### Development and Testing

- **`build-image.sh`**: Build Docker image for the application
- **`run-e2e-tests.sh`**: Run end-to-end tests

## Quick Start

### 1. Production Deployment

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Set up secrets and resources
./scripts/setup-production-secrets.sh -p $PROJECT_ID

# Build and push image
gcloud builds submit --tag gcr.io/$PROJECT_ID/imgstream:latest

# Deploy to production
./scripts/deploy-production.sh -p $PROJECT_ID -i gcr.io/$PROJECT_ID/imgstream:latest
```

### 2. Development Deployment

```bash
# Build image
./scripts/build-image.sh

# Deploy to development
./scripts/deploy-cloud-run.sh -p $PROJECT_ID -e dev -i gcr.io/$PROJECT_ID/imgstream:latest
```

## Script Details

### deploy-production.sh

Complete production deployment script that:
- Validates prerequisites
- Deploys infrastructure with Terraform
- Deploys application to Cloud Run
- Performs health checks
- Provides deployment summary

**Usage:**
```bash
./scripts/deploy-production.sh -p PROJECT_ID -i IMAGE_TAG [OPTIONS]

Options:
  -p PROJECT_ID    GCP project ID (required)
  -i IMAGE_TAG     Docker image tag to deploy (required)
  -r REGION        GCP region [default: us-central1]
  -f               Force deployment without confirmation
  --dry-run        Show deployment commands without executing
  --skip-terraform Skip Terraform infrastructure deployment
  --skip-health    Skip health check after deployment
  -h               Show help message
```

**Examples:**
```bash
# Standard production deployment
./scripts/deploy-production.sh -p my-project -i gcr.io/my-project/imgstream:v1.0.0

# Dry run to see what would be deployed
./scripts/deploy-production.sh -p my-project -i gcr.io/my-project/imgstream:latest --dry-run

# Force deployment without confirmation
./scripts/deploy-production.sh -p my-project -i gcr.io/my-project/imgstream:latest -f

# Skip Terraform (only deploy Cloud Run)
./scripts/deploy-production.sh -p my-project -i gcr.io/my-project/imgstream:latest --skip-terraform
```

### setup-production-secrets.sh

Sets up secrets and resources needed for production:
- Enables required Google Cloud APIs
- Creates secrets in Secret Manager
- Sets up production GCS bucket
- Configures IAM permissions

**Usage:**
```bash
./scripts/setup-production-secrets.sh -p PROJECT_ID [OPTIONS]

Options:
  -p PROJECT_ID    GCP project ID (required)
  -r REGION        GCP region [default: us-central1]
  -f               Force update existing secrets
  --dry-run        Show what would be created without executing
  -h               Show help message
```

**Examples:**
```bash
# Set up production secrets
./scripts/setup-production-secrets.sh -p my-project

# Dry run to see what would be created
./scripts/setup-production-secrets.sh -p my-project --dry-run

# Force update existing secrets
./scripts/setup-production-secrets.sh -p my-project -f
```

### deploy-cloud-run.sh

Deploys the application to Cloud Run for any environment:
- Validates Docker image exists
- Configures environment-specific settings
- Deploys to Cloud Run
- Performs health checks

**Usage:**
```bash
./scripts/deploy-cloud-run.sh -p PROJECT_ID -e ENVIRONMENT -i IMAGE_TAG [OPTIONS]

Options:
  -p PROJECT_ID    GCP project ID (required)
  -e ENVIRONMENT   Environment (dev|prod) (required)
  -i IMAGE_TAG     Docker image tag to deploy (required)
  -r REGION        GCP region [default: us-central1]
  -s SERVICE_NAME  Cloud Run service name [default: imgstream-{env}]
  -f               Force deployment without confirmation
  --dry-run        Show deployment command without executing
  -h               Show help message
```

**Examples:**
```bash
# Deploy to development
./scripts/deploy-cloud-run.sh -p my-project -e dev -i gcr.io/my-project/imgstream:latest

# Deploy to production
./scripts/deploy-cloud-run.sh -p my-project -e prod -i gcr.io/my-project/imgstream:v1.0.0

# Dry run
./scripts/deploy-cloud-run.sh -p my-project -e prod -i gcr.io/my-project/imgstream:latest --dry-run
```

## Prerequisites

Before using these scripts, ensure you have:

1. **Google Cloud SDK**: Installed and authenticated
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Required Tools**:
   - `terraform` (>= 1.0)
   - `docker` (for building images)
   - `curl` (for health checks)

3. **Permissions**: Owner or Editor role on the GCP project

4. **APIs Enabled**: The scripts will enable required APIs automatically

## Environment Variables

The scripts use these environment variables:

- `PROJECT_ID`: Your GCP project ID
- `GOOGLE_CLOUD_PROJECT`: Alternative to PROJECT_ID
- `ENVIRONMENT`: Deployment environment (dev/prod)

## Security Considerations

### Production Deployments

- All production deployments require explicit confirmation
- IAP authentication is enabled by default
- Secrets are stored in Google Secret Manager
- All traffic is encrypted in transit

### Development Deployments

- Public access is enabled for easier testing
- Reduced security policies for development convenience
- Secrets can be provided via environment variables

## Troubleshooting

### Common Issues

1. **Permission Denied**:
   ```bash
   # Ensure you're authenticated
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Image Not Found**:
   ```bash
   # Build and push the image first
   gcloud builds submit --tag gcr.io/$PROJECT_ID/imgstream:latest
   ```

3. **API Not Enabled**:
   ```bash
   # Enable required APIs
   gcloud services enable run.googleapis.com storage.googleapis.com
   ```

4. **Terraform State Issues**:
   ```bash
   # Initialize Terraform
   cd terraform
   terraform init
   ```

### Getting Help

1. **Check Script Help**:
   ```bash
   ./scripts/deploy-production.sh -h
   ```

2. **Enable Debug Mode**:
   ```bash
   # Add debug flag to see detailed output
   bash -x ./scripts/deploy-production.sh -p $PROJECT_ID -i $IMAGE_TAG
   ```

3. **Check Logs**:
   ```bash
   # View Cloud Run logs
   gcloud logs read "resource.type=cloud_run_revision" --limit=50
   ```

## Best Practices

1. **Use Specific Image Tags**: Avoid using `latest` in production
2. **Test in Development First**: Always test deployments in dev environment
3. **Use Dry Run**: Use `--dry-run` to preview changes
4. **Monitor Deployments**: Check health endpoints after deployment
5. **Keep Scripts Updated**: Regularly update scripts with new features

## Contributing

When modifying these scripts:

1. Test in development environment first
2. Update documentation for any new options
3. Follow existing error handling patterns
4. Add appropriate logging and status messages
5. Ensure backward compatibility when possible

---

For more detailed information, see the [Production Deployment Guide](../docs/PRODUCTION_DEPLOYMENT.md).
