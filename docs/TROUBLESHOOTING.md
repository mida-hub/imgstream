# Troubleshooting Guide

This comprehensive guide helps you diagnose and resolve common issues with ImgStream.

## 🔍 Quick Diagnosis

### Health Check Commands

```bash
# Check application health
curl https://your-app-url/health

# Check readiness
curl https://your-app-url/ready

# Check service status
gcloud run services describe imgstream-production --region=us-central1

# View recent logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50
```

### Monitoring Dashboard

Access real-time metrics at:
`https://console.cloud.google.com/monitoring/dashboards`

## 🚨 Common Issues

### 1. Authentication & Authorization

#### Issue: 401 Unauthorized Error

**Symptoms:**
- Users cannot access the application
- API requests return 401 status
- "Access denied" messages in logs

**Diagnosis:**
```bash
# Check IAP configuration
gcloud iap web get-iam-policy --resource-type=backend-services \
  --service=imgstream-production

# Verify user has access
gcloud projects get-iam-policy $GOOGLE_CLOUD_PROJECT \
  --flatten="bindings[].members" \
  --filter="bindings.members:user@example.com"

# Check service account permissions
gcloud iam service-accounts get-iam-policy \
  imgstream-cloud-run-production@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com
```

**Solutions:**

1. **Grant IAP access to users:**
   ```bash
   gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
     --member="user:user@example.com" \
     --role="roles/iap.httpsResourceAccessor"
   ```

2. **Check IAP configuration:**
   ```bash
   # Verify IAP is enabled
   gcloud iap web enable --resource-type=backend-services \
     --service=imgstream-production
   ```

3. **Update service account permissions:**
   ```bash
   gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
     --member="serviceAccount:imgstream-cloud-run-production@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
     --role="roles/run.invoker"
   ```

#### Issue: JWT Token Validation Errors

**Symptoms:**
- "Invalid JWT token" errors
- Authentication works intermittently
- Token expiration issues

**Diagnosis:**
```bash
# Check JWT configuration
curl -H "Authorization: Bearer $TOKEN" \
     https://your-app-url/health

# Verify IAP audience configuration
echo $IAP_AUDIENCE
```

**Solutions:**

1. **Update IAP audience:**
   ```bash
   # Get correct audience from IAP settings
   gcloud iap web get-iam-policy --resource-type=backend-services \
     --service=imgstream-production
   
   # Update environment variable
   gcloud run services update imgstream-production \
     --set-env-vars="IAP_AUDIENCE=your-correct-audience" \
     --region=us-central1
   ```

2. **Refresh authentication:**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

### 2. Storage Issues

#### Issue: Cannot Upload Files

**Symptoms:**
- File upload fails with 500 error
- "Storage not accessible" messages
- Timeout errors during upload

**Diagnosis:**
```bash
# Test bucket access
gsutil ls gs://your-bucket-name

# Check bucket permissions
gsutil iam get gs://your-bucket-name

# Test file upload
gsutil cp test-file.jpg gs://your-bucket-name/test/

# Check service account key
gcloud auth list
```

**Solutions:**

1. **Fix bucket permissions:**
   ```bash
   # Grant storage access to service account
   gsutil iam ch serviceAccount:imgstream-cloud-run-production@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com:objectAdmin \
     gs://your-bucket-name
   ```

2. **Verify bucket configuration:**
   ```bash
   # Check bucket exists
   gsutil mb gs://your-bucket-name
   
   # Set CORS policy
   gsutil cors set cors-config.json gs://your-bucket-name
   ```

3. **Update service configuration:**
   ```bash
   gcloud run services update imgstream-production \
     --set-env-vars="GCS_BUCKET_PRODUCTION=your-bucket-name" \
     --region=us-central1
   ```

#### Issue: Signed URL Generation Fails

**Symptoms:**
- Cannot generate download URLs
- "Insufficient permissions" errors
- URLs expire immediately

**Diagnosis:**
```bash
# Check service account key
gcloud iam service-accounts keys list \
  --iam-account=imgstream-cloud-run-production@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com

# Test signed URL generation
python3 -c "
from google.cloud import storage
client = storage.Client()
bucket = client.bucket('your-bucket-name')
blob = bucket.blob('test-file.jpg')
url = blob.generate_signed_url(expiration=3600)
print(url)
"
```

**Solutions:**

1. **Create new service account key:**
   ```bash
   gcloud iam service-accounts keys create key.json \
     --iam-account=imgstream-cloud-run-production@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com
   ```

2. **Update Cloud Run with new key:**
   ```bash
   gcloud run services update imgstream-production \
     --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json" \
     --region=us-central1
   ```

### 3. Deployment Issues

#### Issue: Cloud Run Deployment Fails

**Symptoms:**
- Build succeeds but deployment fails
- Service doesn't start
- Container exits with error

**Diagnosis:**
```bash
# Check build logs
gcloud builds log [BUILD_ID]

# Check service logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=imgstream-production" \
  --limit=100

# Check service configuration
gcloud run services describe imgstream-production --region=us-central1

# Validate deployment configuration
./scripts/validate-deployment-config.sh production
```

**Solutions:**

1. **Fix container configuration:**
   ```bash
   # Check Dockerfile
   docker build -t test-image .
   docker run --rm test-image
   
   # Update resource limits
   gcloud run services update imgstream-production \
     --memory=2Gi \
     --cpu=2 \
     --region=us-central1
   ```

2. **Fix environment variables:**
   ```bash
   # List current environment variables
   gcloud run services describe imgstream-production \
     --region=us-central1 \
     --format="value(spec.template.spec.template.spec.containers[0].env[].name,spec.template.spec.template.spec.containers[0].env[].value)"
   
   # Update missing variables
   gcloud run services update imgstream-production \
     --set-env-vars="ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT" \
     --region=us-central1
   ```

3. **Rollback to previous version:**
   ```bash
   # List revisions
   gcloud run revisions list --service=imgstream-production --region=us-central1
   
   # Rollback to previous revision
   gcloud run services update-traffic imgstream-production \
     --to-revisions=PREVIOUS_REVISION=100 \
     --region=us-central1
   ```

#### Issue: GitHub Actions Deployment Fails

**Symptoms:**
- CI/CD pipeline fails
- Authentication errors in GitHub Actions
- Build or test failures

**Diagnosis:**
```bash
# Check GitHub Actions logs
# Visit: https://github.com/your-org/imgstream/actions

# Verify GitHub secrets
# Check: Repository Settings > Secrets and variables > Actions

# Test local build
docker build -t imgstream .
uv run pytest
```

**Solutions:**

1. **Update GitHub secrets:**
   - `GCP_SA_KEY`: Service account key JSON
   - `GOOGLE_CLOUD_PROJECT`: Project ID
   - `GCS_BUCKET_PRODUCTION`: Production bucket name

2. **Fix service account permissions:**
   ```bash
   # Grant required roles
   gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
     --member="serviceAccount:github-actions@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
     --role="roles/run.admin"
   
   gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
     --member="serviceAccount:github-actions@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   ```

3. **Fix workflow configuration:**
   ```yaml
   # .github/workflows/deploy.yml
   - name: Authenticate to Google Cloud
     uses: google-github-actions/auth@v2
     with:
       credentials_json: ${{ secrets.GCP_SA_KEY }}
   ```

### 4. Performance Issues

#### Issue: Slow Response Times

**Symptoms:**
- High response times (>2 seconds)
- Timeout errors
- Poor user experience

**Diagnosis:**
```bash
# Check monitoring dashboard
# https://console.cloud.google.com/monitoring

# Analyze performance
./scripts/deployment-monitor.sh status

# Check resource usage
gcloud run services describe imgstream-production \
  --region=us-central1 \
  --format="value(status.conditions[0].message)"

# Load test
curl -w "@curl-format.txt" -o /dev/null -s https://your-app-url/health
```

**Solutions:**

1. **Increase resources:**
   ```bash
   gcloud run services update imgstream-production \
     --memory=4Gi \
     --cpu=2 \
     --region=us-central1
   ```

2. **Optimize concurrency:**
   ```bash
   gcloud run services update imgstream-production \
     --concurrency=100 \
     --region=us-central1
   ```

3. **Scale instances:**
   ```bash
   gcloud run services update imgstream-production \
     --min-instances=2 \
     --max-instances=100 \
     --region=us-central1
   ```

#### Issue: High Memory Usage

**Symptoms:**
- Memory usage >80%
- Out of memory errors
- Container restarts

**Diagnosis:**
```bash
# Check memory metrics
gcloud monitoring metrics list --filter="metric.type:memory"

# Check container logs for OOM
gcloud logs read "resource.type=cloud_run_revision" \
  --filter="textPayload:memory" \
  --limit=50
```

**Solutions:**

1. **Increase memory limit:**
   ```bash
   gcloud run services update imgstream-production \
     --memory=4Gi \
     --region=us-central1
   ```

2. **Optimize image processing:**
   ```python
   # Reduce image quality for thumbnails
   thumbnail_quality = 75
   
   # Process images in batches
   batch_size = 5
   ```

3. **Implement caching:**
   ```python
   # Add Redis or in-memory caching
   from functools import lru_cache
   
   @lru_cache(maxsize=100)
   def process_image(image_path):
       # Image processing logic
       pass
   ```

### 5. Database Issues

#### Issue: Database Connection Errors

**Symptoms:**
- "Database connection failed" errors
- Data not persisting
- Query timeouts

**Diagnosis:**
```bash
# Test database connection
python3 -c "
import duckdb
conn = duckdb.connect(':memory:')
print(conn.execute('SELECT 1').fetchone())
conn.close()
"

# Check database file permissions
ls -la data/

# Check disk space
df -h
```

**Solutions:**

1. **Fix database path:**
   ```bash
   # Ensure data directory exists
   mkdir -p data/
   chmod 755 data/
   ```

2. **Update database configuration:**
   ```yaml
   # config/environments/production.yaml
   database:
     type: "sqlite"
     path: "./data/imgstream_prod.db"
     auto_migrate: true
   ```

3. **Initialize database:**
   ```bash
   uv run python -c "
   from src.imgstream.database import init_database
   init_database()
   "
   ```

### 6. Monitoring & Alerting Issues

#### Issue: No Metrics or Alerts

**Symptoms:**
- Empty monitoring dashboard
- No alert notifications
- Missing metrics data

**Diagnosis:**
```bash
# Check monitoring setup
./scripts/setup-monitoring.sh

# Verify Cloud Monitoring API
gcloud services list --enabled --filter="name:monitoring.googleapis.com"

# Check alert policies
gcloud alpha monitoring policies list
```

**Solutions:**

1. **Enable required APIs:**
   ```bash
   gcloud services enable monitoring.googleapis.com
   gcloud services enable logging.googleapis.com
   ```

2. **Set up monitoring:**
   ```bash
   ENVIRONMENT=production ./scripts/setup-monitoring.sh
   ```

3. **Configure notification channels:**
   ```bash
   # Update email for alerts
   export ALERT_EMAIL="ops@example.com"
   ./scripts/setup-monitoring.sh
   ```

#### Issue: False Positive Alerts

**Symptoms:**
- Too many alert notifications
- Alerts for normal behavior
- Alert fatigue

**Solutions:**

1. **Adjust alert thresholds:**
   ```bash
   # Update alert policies
   gcloud alpha monitoring policies update POLICY_ID \
     --policy-from-file=updated-policy.json
   ```

2. **Add alert conditions:**
   ```yaml
   # Require multiple consecutive failures
   conditions:
     duration: "600s"  # 10 minutes instead of 5
   ```

3. **Configure alert suppression:**
   ```bash
   # Set up maintenance windows
   gcloud alpha monitoring policies update POLICY_ID \
     --notification-channels=""
   ```

## 🔧 Diagnostic Tools

### Log Analysis

```bash
# Search for specific errors
gcloud logs read "resource.type=cloud_run_revision" \
  --filter="severity>=ERROR" \
  --limit=100

# Filter by time range
gcloud logs read "resource.type=cloud_run_revision" \
  --filter="timestamp>=\"2024-01-01T00:00:00Z\"" \
  --limit=50

# Export logs for analysis
gcloud logs read "resource.type=cloud_run_revision" \
  --format="json" > logs.json
```

### Performance Monitoring

```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s https://your-app-url/

# Load testing
for i in {1..100}; do
  curl -s https://your-app-url/health > /dev/null &
done
wait
```

### Health Check Script

```bash
#!/bin/bash
# health-check.sh

URL="https://your-app-url"

echo "Checking application health..."

# Basic connectivity
if curl -f "$URL/health" > /dev/null 2>&1; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi

# Check response time
RESPONSE_TIME=$(curl -w "%{time_total}" -o /dev/null -s "$URL/health")
echo "Response time: ${RESPONSE_TIME}s"

if (( $(echo "$RESPONSE_TIME > 2.0" | bc -l) )); then
    echo "⚠️  Slow response time"
fi

echo "Health check complete"
```

## 📞 Getting Help

### Self-Service Resources

1. **Check documentation**: `docs/` directory
2. **Review logs**: Use `gcloud logs read` commands
3. **Monitor dashboard**: Cloud Console > Monitoring
4. **Run diagnostics**: `./scripts/validate-deployment-config.sh`

### Escalation Process

1. **Level 1**: Check this troubleshooting guide
2. **Level 2**: Review application logs and metrics
3. **Level 3**: Create GitHub issue with:
   - Error messages
   - Steps to reproduce
   - Environment details
   - Log excerpts

### Emergency Contacts

- **Production Issues**: ops@example.com
- **Security Issues**: security@example.com
- **Development Team**: dev@example.com

### Useful Commands Reference

```bash
# Quick health check
curl https://your-app-url/health

# View service status
gcloud run services list

# Check recent deployments
gcloud run revisions list --service=imgstream-production

# Monitor real-time logs
gcloud logs tail "resource.type=cloud_run_revision"

# Emergency rollback
./scripts/deployment-monitor.sh rollback

# Restart service (redeploy current revision)
gcloud run services update imgstream-production --region=us-central1

# Scale service
gcloud run services update imgstream-production \
  --min-instances=5 --max-instances=50 --region=us-central1
```

---

**Remember**: When in doubt, check the logs first! Most issues can be diagnosed through careful log analysis and monitoring dashboard review.
