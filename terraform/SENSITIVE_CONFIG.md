# Sensitive Configuration Management

This document explains how to manage sensitive information (like email addresses) in a public repository.

## Problem

The Terraform configuration requires personal email addresses for:
- `allowed_users`: Users who can access the application via IAP
- `iap_support_email`: Support email for OAuth consent screen
- `alert_email`: Email for monitoring alerts

Since this is a public repository, we cannot commit personal email addresses to version control.

## Solutions

### Option 1: Environment Variables (Recommended)

Set sensitive values as environment variables before running Terraform:

```bash
# Development environment
export TF_VAR_allowed_users='["dev1@example.com","dev2@example.com"]'
export TF_VAR_iap_support_email="dev-support@example.com"
export TF_VAR_alert_email="dev-alerts@example.com"

cd terraform/dev
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

```bash
# Production environment
export TF_VAR_allowed_users='["admin@example.com","ops@example.com"]'
export TF_VAR_iap_support_email="support@example.com"
export TF_VAR_alert_email="alerts@example.com"

cd terraform/prod
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

### Option 2: Local Configuration Files

Create local configuration files that are automatically ignored by git:

```bash
# Development
cd terraform/dev
cp terraform.tfvars.local.example terraform.tfvars.local
# Edit terraform.tfvars.local with your actual values
vim terraform.tfvars.local

# The deploy script will automatically include this file
terraform/scripts/deploy.sh -e dev -a apply
```

```bash
# Production
cd terraform/prod
cp terraform.tfvars.local.example terraform.tfvars.local
# Edit terraform.tfvars.local with your actual values
vim terraform.tfvars.local

# The deploy script will automatically include this file
terraform/scripts/deploy.sh -e prod -a apply
```

### Option 3: CI/CD Secrets

For automated deployments, store sensitive values as secrets in your CI/CD system:

#### GitHub Actions
1. Go to your repository settings
2. Navigate to Secrets and variables → Actions
3. Add repository secrets:
   - `TF_VAR_ALLOWED_USERS_DEV`
   - `TF_VAR_IAP_SUPPORT_EMAIL_DEV`
   - `TF_VAR_ALERT_EMAIL_DEV`
   - `TF_VAR_ALLOWED_USERS_PROD`
   - `TF_VAR_IAP_SUPPORT_EMAIL_PROD`
   - `TF_VAR_ALERT_EMAIL_PROD`

#### Example GitHub Actions workflow:
```yaml
- name: Deploy to Development
  env:
    TF_VAR_allowed_users: ${{ secrets.TF_VAR_ALLOWED_USERS_DEV }}
    TF_VAR_iap_support_email: ${{ secrets.TF_VAR_IAP_SUPPORT_EMAIL_DEV }}
    TF_VAR_alert_email: ${{ secrets.TF_VAR_ALERT_EMAIL_DEV }}
  run: |
    cd terraform/dev
    terraform apply -var-file=dev.tfvars -auto-approve
```

## File Structure

```
terraform/
├── dev/
│   ├── dev.tfvars                      # Public configuration
│   ├── terraform.tfvars.local.example  # Template for local config
│   └── terraform.tfvars.local          # Local config (gitignored)
├── prod/
│   ├── prod.tfvars                     # Public configuration
│   ├── terraform.tfvars.local.example  # Template for local config
│   └── terraform.tfvars.local          # Local config (gitignored)
```

## Security Best Practices

1. **Never commit sensitive data**: Always use environment variables or local files
2. **Use example files**: Provide `.example` files to show the expected format
3. **Document clearly**: Make it obvious what values need to be set locally
4. **Validate in CI**: Ensure your CI/CD pipeline can deploy without committed secrets
5. **Regular rotation**: Periodically rotate sensitive values

## Troubleshooting

### Missing Variables Error
If you see errors like "variable not defined", ensure you've set the required environment variables or created the local configuration file.

### Permission Denied
If IAP access is denied, verify that your email address is correctly set in the `allowed_users` variable.

### Email Format
Ensure email addresses are in the correct format:
```bash
# Correct
export TF_VAR_allowed_users='["user@example.com","admin@example.com"]'

# Incorrect
export TF_VAR_allowed_users="user@example.com,admin@example.com"
```
