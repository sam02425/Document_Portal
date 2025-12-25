# Document Portal - Deployment Guide

This guide covers deployment of the Document Portal API to various environments including Docker, cloud platforms, and production configurations.

---

## Table of Contents

1. [Quick Start with Docker](#quick-start-with-docker)
2. [Environment Configuration](#environment-configuration)
3. [Production Deployment](#production-deployment)
4. [Cloud Platform Deployment](#cloud-platform-deployment)
5. [Monitoring & Performance](#monitoring--performance)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start with Docker

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum (8GB recommended)
- 10GB disk space

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/Document_Portal.git
cd Document_Portal
```

### Step 2: Configure Environment

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# API Keys
GOOGLE_API_KEY=your-google-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here

# Application Settings
LOG_LEVEL=INFO
WORKERS=4
MAX_UPLOAD_SIZE=10485760  # 10MB in bytes

# Optional: Database (if using PostgreSQL)
# DB_PASSWORD=secure-password-here

# Optional: Grafana (if using monitoring)
# GRAFANA_PASSWORD=admin-password-here
```

### Step 3: Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the services
docker-compose up -d

# View logs
docker-compose logs -f api
```

### Step 4: Verify Deployment

```bash
# Health check
curl http://localhost:8000/

# Expected response:
# {"status":"ok","service":"Document Portal","version":"2.0.0"}

# Access Swagger UI
open http://localhost:8000/docs
```

### Step 5: Stop Services

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

---

## Environment Configuration

### Required Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GOOGLE_API_KEY` | Google Gemini API key | - | Yes* |
| `GEMINI_API_KEY` | Alternative to GOOGLE_API_KEY | - | Yes* |

*Required for Gemini Vision features (name/address extraction)

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `WORKERS` | Number of Uvicorn workers | 4 |
| `MAX_UPLOAD_SIZE` | Max file upload size (bytes) | 10485760 (10MB) |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | * |
| `CACHE_TTL` | Cache time-to-live (seconds) | 86400 (24h) |

### Example `.env` File

```env
# Production Configuration
GOOGLE_API_KEY=AIzaSyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY  # Example key
LOG_LEVEL=INFO
WORKERS=8
MAX_UPLOAD_SIZE=20971520  # 20MB
CORS_ORIGINS=https://app.example.com,https://dashboard.example.com
CACHE_TTL=43200  # 12 hours
```

---

## Production Deployment

### Option 1: Docker (Recommended)

#### Build Production Image

```bash
# Build with production tag
docker build -t document-portal:production .

# Tag for registry
docker tag document-portal:production your-registry.com/document-portal:2.0.0

# Push to registry
docker push your-registry.com/document-portal:2.0.0
```

#### Run in Production

```bash
docker run -d \
  --name document-portal-api \
  -p 8000:8000 \
  -e GOOGLE_API_KEY=$GOOGLE_API_KEY \
  -e LOG_LEVEL=INFO \
  -e WORKERS=8 \
  -v /data/uploads:/app/temp_uploads \
  -v /data/results:/app/results \
  -v /data/cache:/app/data \
  --restart unless-stopped \
  your-registry.com/document-portal:2.0.0
```

### Option 2: Direct Installation

#### Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.10 python3-pip tesseract-ocr poppler-utils

# RHEL/CentOS
sudo yum install -y python3 python3-pip tesseract poppler-utils
```

#### Install Python Dependencies

```bash
pip install -r requirements.txt
```

#### Run with Uvicorn

```bash
# Development
uvicorn api.main:app --reload

# Production
uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 8 \
  --log-level info \
  --access-log
```

#### Systemd Service (Linux)

Create `/etc/systemd/system/document-portal.service`:

```ini
[Unit]
Description=Document Portal API
After=network.target

[Service]
Type=simple
User=docportal
WorkingDirectory=/opt/document-portal
Environment="GOOGLE_API_KEY=your-key-here"
Environment="LOG_LEVEL=INFO"
ExecStart=/usr/local/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 8
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable document-portal
sudo systemctl start document-portal
sudo systemctl status document-portal
```

---

## Cloud Platform Deployment

### AWS (ECS/Fargate)

#### 1. Create ECR Repository

```bash
aws ecr create-repository --repository-name document-portal
```

#### 2. Push Image to ECR

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag document-portal:production 123456789012.dkr.ecr.us-east-1.amazonaws.com/document-portal:2.0.0
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/document-portal:2.0.0
```

#### 3. Create ECS Task Definition

Use `infrastructure/document-portal-cf.yaml` (already included in repo)

```bash
aws cloudformation create-stack \
  --stack-name document-portal \
  --template-body file://infrastructure/document-portal-cf.yaml \
  --parameters ParameterKey=GoogleApiKey,ParameterValue=$GOOGLE_API_KEY
```

#### 4. Deploy to Fargate

```bash
aws ecs create-service \
  --cluster document-portal-cluster \
  --service-name document-portal-api \
  --task-definition document-portal:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345],assignPublicIp=ENABLED}"
```

### Google Cloud (Cloud Run)

#### 1. Build and Push to GCR

```bash
# Build for Cloud Run
gcloud builds submit --tag gcr.io/your-project/document-portal

# Or manually
docker tag document-portal:production gcr.io/your-project/document-portal:2.0.0
docker push gcr.io/your-project/document-portal:2.0.0
```

#### 2. Deploy to Cloud Run

```bash
gcloud run deploy document-portal \
  --image gcr.io/your-project/document-portal:2.0.0 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY,LOG_LEVEL=INFO \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 10
```

### Azure (Container Instances)

#### 1. Push to ACR

```bash
# Create registry
az acr create --resource-group myResourceGroup --name docportalregistry --sku Basic

# Login
az acr login --name docportalregistry

# Tag and push
docker tag document-portal:production docportalregistry.azurecr.io/document-portal:2.0.0
docker push docportalregistry.azurecr.io/document-portal:2.0.0
```

#### 2. Deploy Container

```bash
az container create \
  --resource-group myResourceGroup \
  --name document-portal-api \
  --image docportalregistry.azurecr.io/document-portal:2.0.0 \
  --cpu 2 --memory 4 \
  --ports 8000 \
  --environment-variables GOOGLE_API_KEY=$GOOGLE_API_KEY LOG_LEVEL=INFO \
  --restart-policy Always
```

### Kubernetes (K8s)

#### Deployment YAML

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: document-portal-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: document-portal
  template:
    metadata:
      labels:
        app: document-portal
    spec:
      containers:
      - name: api
        image: your-registry.com/document-portal:2.0.0
        ports:
        - containerPort: 8000
        env:
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: google-api-key
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: document-portal-service
spec:
  selector:
    app: document-portal
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

Deploy:

```bash
# Create secret for API key
kubectl create secret generic api-keys --from-literal=google-api-key=$GOOGLE_API_KEY

# Deploy
kubectl apply -f k8s/deployment.yaml

# Check status
kubectl get pods
kubectl get services
```

---

## Monitoring & Performance

### Health Checks

#### Basic Health Check

```bash
curl http://localhost:8000/
```

#### Detailed Health Check

```python
# Add to api/main.py
@app.get("/health", tags=["health"])
def detailed_health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "gemini_api": check_gemini_connection(),
            "tesseract": check_tesseract(),
            "disk_space": check_disk_space()
        }
    }
```

### Logging

Logs are output to stdout in JSON format (via structlog).

**View logs in Docker:**

```bash
docker-compose logs -f api
```

**Production log aggregation:**

Use Fluentd, Logstash, or CloudWatch Logs Agent to collect logs.

### Metrics (Future Enhancement)

Add Prometheus metrics:

```python
from prometheus_fastapi_instrumentator import Instrumentator

@app.on_event("startup")
async def startup():
    Instrumentator().instrument(app).expose(app)
```

Access metrics at: `http://localhost:8000/metrics`

### Performance Tuning

#### Optimize Uvicorn Workers

```bash
# Calculate workers: (2 × CPU cores) + 1
# For 4 cores: (2 × 4) + 1 = 9 workers
uvicorn api.main:app --workers 9
```

#### Enable Gunicorn

For production, use Gunicorn with Uvicorn workers:

```bash
gunicorn api.main:app \
  --workers 9 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

#### Memory Limits

Set container memory limits:

```bash
docker run -m 4g --memory-swap 4g ...
```

---

## Troubleshooting

### Common Issues

#### 1. Tesseract Not Found

**Error:** `TesseractNotFoundError`

**Solution:**

```bash
# Install Tesseract
sudo apt-get install tesseract-ocr

# Verify installation
tesseract --version
```

#### 2. Gemini API Key Invalid

**Error:** `API key not valid`

**Solution:**

```bash
# Check environment variable
echo $GOOGLE_API_KEY

# Test API key
curl -H "Authorization: Bearer $GOOGLE_API_KEY" \
  https://generativelanguage.googleapis.com/v1/models
```

#### 3. Out of Memory

**Error:** Container killed or `MemoryError`

**Solution:**

```bash
# Increase Docker memory limit
docker run -m 8g ...

# Reduce workers
uvicorn api.main:app --workers 2

# Enable swap
docker run --memory-swap 8g ...
```

#### 4. Slow Image Processing

**Solution:**

- Reduce `max_dimension` in scanner settings
- Use smaller batch sizes for invoices
- Enable caching with `user_id`
- Consider adding Redis for distributed caching

#### 5. Permission Denied (File I/O)

**Solution:**

```bash
# Fix permissions
chmod 777 temp_uploads/ results/ data/

# Or run as specific user
docker run --user 1000:1000 ...
```

---

## Security Best Practices

### 1. API Key Management

✅ **DO:**
- Store API keys in environment variables or secret managers (AWS Secrets Manager, Google Secret Manager, Azure Key Vault)
- Rotate keys regularly (every 90 days)
- Use different keys for dev/staging/production

❌ **DON'T:**
- Hardcode API keys in code
- Commit `.env` files to git
- Share keys in documentation

### 2. Network Security

✅ **DO:**
- Use HTTPS in production (terminate SSL at load balancer or reverse proxy)
- Restrict CORS origins in production (remove `allow_origins=["*"]`)
- Implement rate limiting
- Use firewall rules to restrict access

### 3. Container Security

✅ **DO:**
- Run as non-root user (already configured in Dockerfile)
- Keep base images updated
- Scan images for vulnerabilities (`docker scan`)
- Use minimal base images (alpine, slim)

### 4. Data Security

✅ **DO:**
- Enable encryption at rest for volumes
- Use HTTPS for all API calls
- Implement data retention policies
- Auto-delete temp files (already implemented)

---

## Scaling

### Horizontal Scaling

**Docker Swarm:**

```bash
docker service create \
  --name document-portal \
  --replicas 5 \
  --publish 8000:8000 \
  your-registry.com/document-portal:2.0.0
```

**Kubernetes:**

```bash
kubectl scale deployment document-portal-api --replicas=10
```

### Load Balancing

Use Nginx or HAProxy:

**Nginx config:**

```nginx
upstream document_portal {
    least_conn;
    server api1:8000;
    server api2:8000;
    server api3:8000;
}

server {
    listen 80;
    server_name api.documentportal.com;

    location / {
        proxy_pass http://document_portal;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Backup & Disaster Recovery

### Backup Strategy

**What to backup:**
- User cache data (`data/user_cache.json`)
- Extraction results (`results/`)
- Configuration files (`.env`, `config/config.yaml`)

**Backup script:**

```bash
#!/bin/bash
BACKUP_DIR="/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

docker cp document-portal-api:/app/data $BACKUP_DIR/
docker cp document-portal-api:/app/results $BACKUP_DIR/

tar -czf $BACKUP_DIR/backup.tar.gz $BACKUP_DIR/data $BACKUP_DIR/results
```

### Restore

```bash
docker cp backup/data/ document-portal-api:/app/data
docker cp backup/results/ document-portal-api:/app/results
docker restart document-portal-api
```

---

## Support & Contact

For deployment assistance:
- 📧 Email: devops@documentportal.com
- 📖 Docs: https://docs.documentportal.com
- 🐛 Issues: GitHub repository

---

**Document Portal v2.0.0**
*Production-Ready Deployment Guide*
