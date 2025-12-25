# Document Portal - Monitoring & Performance Metrics Guide

## Overview

This guide covers monitoring, performance tracking, and observability for the Document Portal API in production environments.

---

## Table of Contents

1. [Quick Setup](#quick-setup)
2. [Application Metrics](#application-metrics)
3. [Health Checks](#health-checks)
4. [Logging Strategy](#logging-strategy)
5. [Error Tracking](#error-tracking)
6. [Performance Monitoring](#performance-monitoring)
7. [Alerting](#alerting)

---

## Quick Setup

### Enable Prometheus Metrics

Add to `requirements.txt`:

```
prometheus-fastapi-instrumentator==6.1.0
```

Add to `api/main.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

@app.on_event("startup")
async def startup():
    Instrumentator().instrument(app).expose(app)
```

Access metrics:

```
http://localhost:8000/metrics
```

---

## Application Metrics

### Key Metrics to Track

#### 1. Request Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | Request latency |
| `http_requests_in_progress` | Gauge | Active requests |
| `http_request_size_bytes` | Histogram | Request body size |
| `http_response_size_bytes` | Histogram | Response body size |

#### 2. ID Extraction Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Extraction attempts
id_extractions_total = Counter(
    'id_extractions_total',
    'Total ID extraction attempts',
    ['method', 'status']
)

# Extraction duration
id_extraction_duration = Histogram(
    'id_extraction_duration_seconds',
    'ID extraction duration',
    ['method']
)

# Confidence scores
id_confidence_score = Histogram(
    'id_confidence_score',
    'ID extraction confidence scores',
    buckets=[0, 50, 70, 80, 90, 95, 100]
)
```

#### 3. Invoice Processing Metrics

```python
# Invoice extractions
invoice_extractions_total = Counter(
    'invoice_extractions_total',
    'Total invoice extractions',
    ['doc_type', 'method']
)

# Line items extracted
invoice_line_items = Histogram(
    'invoice_line_items_count',
    'Number of line items per invoice'
)

# Invoice merging
invoice_merge_operations = Counter(
    'invoice_merge_operations_total',
    'Total invoice merge operations',
    ['result']
)
```

#### 4. System Metrics

```python
# Temp file cleanup
temp_files_cleaned = Counter(
    'temp_files_cleaned_total',
    'Total temporary files cleaned up'
)

# Cache hits/misses
cache_operations = Counter(
    'cache_operations_total',
    'Cache operations',
    ['operation', 'result']
)

# Compression operations
compression_operations = Histogram(
    'compression_ratio',
    'Image compression ratios achieved'
)
```

### Implementing Metrics

Create `utils/metrics.py`:

```python
"""Prometheus metrics for Document Portal."""
from prometheus_client import Counter, Histogram, Gauge
from functools import wraps
import time

# Define metrics
REQUEST_COUNTER = Counter(
    'document_portal_requests_total',
    'Total requests',
    ['endpoint', 'method', 'status']
)

EXTRACTION_DURATION = Histogram(
    'extraction_duration_seconds',
    'Extraction operation duration',
    ['operation_type']
)

CONFIDENCE_SCORE = Histogram(
    'confidence_score',
    'Extraction confidence scores',
    ['extraction_type'],
    buckets=[0, 50, 60, 70, 80, 90, 95, 100]
)

# Decorator for timing operations
def track_duration(operation_type):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                EXTRACTION_DURATION.labels(operation_type=operation_type).observe(duration)
        return wrapper
    return decorator

# Decorator for tracking confidence
def track_confidence(extraction_type):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            if 'confidence' in result:
                CONFIDENCE_SCORE.labels(extraction_type=extraction_type).observe(result['confidence'])
            return result
        return wrapper
    return decorator
```

Usage in endpoints:

```python
from utils.metrics import track_duration, track_confidence, REQUEST_COUNTER

@app.post("/extract/id")
@track_duration("id_extraction")
@track_confidence("id")
async def extract_id_endpoint(...):
    # ... existing code ...
    REQUEST_COUNTER.labels(endpoint='extract_id', method='POST', status='success').inc()
    return result
```

---

## Health Checks

### Basic Health Check

Already implemented:

```bash
curl http://localhost:8000/
```

### Advanced Health Check

Add to `api/main.py`:

```python
from datetime import datetime
import psutil
import os

@app.get("/health/live", tags=["health"])
def liveness_probe():
    """Kubernetes liveness probe."""
    return {"status": "alive", "timestamp": datetime.now().isoformat()}

@app.get("/health/ready", tags=["health"])
def readiness_probe():
    """Kubernetes readiness probe with dependency checks."""
    checks = {
        "api": "healthy",
        "disk_space": check_disk_space(),
        "memory": check_memory(),
        "gemini_api": check_gemini_connectivity(),
        "tesseract": check_tesseract()
    }

    all_healthy = all(v == "healthy" for v in checks.values())

    return {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }

def check_disk_space() -> str:
    """Check if disk space is sufficient."""
    usage = psutil.disk_usage('/')
    if usage.percent < 90:
        return "healthy"
    return f"warning: {usage.percent}% used"

def check_memory() -> str:
    """Check memory usage."""
    memory = psutil.virtual_memory()
    if memory.percent < 90:
        return "healthy"
    return f"warning: {memory.percent}% used"

def check_gemini_connectivity() -> str:
    """Check if Gemini API is accessible."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "not_configured"
    # Add actual connectivity check here
    return "healthy"

def check_tesseract() -> str:
    """Check if Tesseract OCR is installed."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return "healthy"
    except Exception:
        return "unavailable"
```

---

## Logging Strategy

### Structured Logging

Document Portal uses `structlog` for JSON-formatted logs.

**Log Levels:**
- `DEBUG`: Detailed debugging information
- `INFO`: General informational messages
- `WARNING`: Warning messages (non-critical)
- `ERROR`: Error messages (handled)
- `CRITICAL`: Critical errors (system failures)

**Example Log Entry:**

```json
{
  "event": "id_extraction_completed",
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "info",
  "filename": "id.jpg",
  "method": "gemini_vision",
  "confidence": 95,
  "duration_ms": 1234,
  "user_id": "user123"
}
```

### Log Aggregation

#### Option 1: ELK Stack (Elasticsearch, Logstash, Kibana)

**docker-compose.yml addition:**

```yaml
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
  environment:
    - discovery.type=single-node
  ports:
    - "9200:9200"

logstash:
  image: docker.elastic.co/logstash/logstash:8.11.0
  volumes:
    - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
  depends_on:
    - elasticsearch

kibana:
  image: docker.elastic.co/kibana/kibana:8.11.0
  ports:
    - "5601:5601"
  depends_on:
    - elasticsearch
```

#### Option 2: CloudWatch Logs (AWS)

Install CloudWatch agent:

```bash
pip install watchtower
```

Configure in `logger.py`:

```python
import watchtower
import logging

logger = logging.getLogger()
logger.addHandler(watchtower.CloudWatchLogHandler(
    log_group='/document-portal/api',
    stream_name='production'
))
```

#### Option 3: Google Cloud Logging

```bash
pip install google-cloud-logging
```

```python
from google.cloud import logging as gcp_logging

client = gcp_logging.Client()
client.setup_logging()
```

---

## Error Tracking

### Sentry Integration

#### Install Sentry SDK

```bash
pip install sentry-sdk[fastapi]
```

#### Configure in `api/main.py`

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENVIRONMENT", "production"),
    traces_sample_rate=0.1,  # 10% of transactions
    integrations=[FastApiIntegration()]
)
```

#### Track Custom Events

```python
from sentry_sdk import capture_exception, capture_message

try:
    result = id_extractor.extract_id_data(text)
except Exception as e:
    capture_exception(e)
    raise

# Track low confidence extractions
if result['confidence'] < 50:
    capture_message(
        f"Low confidence extraction: {result['confidence']}%",
        level="warning"
    )
```

---

## Performance Monitoring

### Response Time Tracking

Add middleware to track all requests:

```python
import time
from starlette.middleware.base import BaseHTTPMiddleware

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        response.headers["X-Process-Time"] = str(duration)

        log.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration
        )

        return response

app.add_middleware(TimingMiddleware)
```

### Database Query Performance

If using PostgreSQL (future enhancement):

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info['query_start_time'].pop(-1)
    log.info("query_executed", duration_seconds=total, statement=statement[:100])
```

### APM (Application Performance Monitoring)

#### New Relic

```bash
pip install newrelic
```

```bash
NEW_RELIC_CONFIG_FILE=newrelic.ini newrelic-admin run-program uvicorn api.main:app
```

#### Datadog

```bash
pip install ddtrace
```

```bash
ddtrace-run uvicorn api.main:app
```

---

## Alerting

### Prometheus Alerting Rules

Create `monitoring/alerts.yml`:

```yaml
groups:
  - name: document_portal
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} per second"

      # Slow requests
      - alert: SlowRequests
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 5
        for: 5m
        annotations:
          summary: "95th percentile latency is high"
          description: "P95 latency is {{ $value }} seconds"

      # Low confidence extractions
      - alert: LowConfidenceExtractions
        expr: avg(confidence_score{extraction_type="id"}) < 70
        for: 10m
        annotations:
          summary: "Average ID extraction confidence is low"
          description: "Average confidence: {{ $value }}%"

      # High memory usage
      - alert: HighMemoryUsage
        expr: (process_resident_memory_bytes / node_memory_MemTotal_bytes) > 0.9
        for: 5m
        annotations:
          summary: "Memory usage is above 90%"
```

### PagerDuty Integration

```python
import requests

def send_pagerduty_alert(severity, summary, details):
    """Send alert to PagerDuty."""
    payload = {
        "routing_key": os.getenv("PAGERDUTY_ROUTING_KEY"),
        "event_action": "trigger",
        "payload": {
            "summary": summary,
            "severity": severity,  # critical, error, warning, info
            "source": "document-portal-api",
            "custom_details": details
        }
    }

    requests.post(
        "https://events.pagerduty.com/v2/enqueue",
        json=payload
    )
```

Usage:

```python
if extraction_failures > 10:
    send_pagerduty_alert(
        severity="error",
        summary="High extraction failure rate",
        details={"failures": extraction_failures, "time_window": "5m"}
    )
```

---

## Dashboard Examples

### Grafana Dashboard JSON

Sample metrics to display:

1. **Request Rate**: `rate(http_requests_total[5m])`
2. **Error Rate**: `rate(http_requests_total{status=~"5.."}[5m])`
3. **P95 Latency**: `histogram_quantile(0.95, http_request_duration_seconds)`
4. **Average Confidence**: `avg(confidence_score)`
5. **Cache Hit Rate**: `rate(cache_operations_total{result="hit"}[5m]) / rate(cache_operations_total[5m])`

---

## Best Practices

### ✅ DO:
- Set up alerts for critical failures
- Monitor P95/P99 latency (not just average)
- Track confidence scores over time
- Log all errors with context
- Set up automated health checks

### ❌ DON'T:
- Log sensitive data (PII, API keys)
- Ignore warning-level alerts
- Set too many alerts (alert fatigue)
- Monitor everything (focus on key metrics)

---

## Monitoring Checklist

- [ ] Prometheus metrics enabled
- [ ] Health check endpoints configured
- [ ] Structured logging implemented
- [ ] Error tracking (Sentry) configured
- [ ] Alerting rules defined
- [ ] Dashboards created
- [ ] On-call rotation established
- [ ] Runbook created for common issues

---

**Document Portal v2.0.0**
*Complete Monitoring & Metrics Guide*
