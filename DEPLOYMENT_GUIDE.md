# 🚀 Deploying MCP Servers in Production

> A practical guide to deploying MCP servers and multi-agent systems in production environments, with a focus on Google Cloud Platform but applicable to any cloud provider.

---

## Table of Contents

- [The Fundamental Principle](#the-fundamental-principle)
- [Why Separate Deployment Matters](#why-separate-deployment-matters)
- [Architecture Patterns](#architecture-patterns)
- [Deploying on Google Cloud Platform](#deploying-on-google-cloud-platform)
- [Deploying on AWS](#deploying-on-aws)
- [Deploying on Azure](#deploying-on-azure)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Building MCP Servers for Cloud Services](#building-mcp-servers-for-cloud-services)
- [Environment Configuration](#environment-configuration)
- [Security Best Practices](#security-best-practices)
- [Monitoring and Observability](#monitoring-and-observability)
- [Scaling Considerations](#scaling-considerations)
- [CI/CD Pipeline](#cicd-pipeline)
- [Cost Optimization](#cost-optimization)
- [Production Checklist](#production-checklist)

---

## The Fundamental Principle

**Always deploy MCP servers and agent systems as separate, independent services.**

```
❌ ANTI-PATTERN: Everything in one container
┌─────────────────────────────────────────┐
│         Monolithic Container            │
│                                         │
│  • Multi-Agent System                   │
│  • MCP Server 1                         │
│  • MCP Server 2                         │
│  • MCP Server 3                         │
│  • All tightly coupled                  │
└─────────────────────────────────────────┘
Problems: Can't scale independently, 
can't update independently, single point 
of failure, no reusability
```

```
✅ BEST PRACTICE: Separate services
┌──────────────────┐
│  Multi-Agent     │  ← Agent with MCP clients
│  System          │
│  (Cloud Run)     │
└────────┬─────────┘
         │
    ┌────┼────┬────┬────┐
    │    │    │    │    │
    ▼    ▼    ▼    ▼    ▼
  ┌───┐┌───┐┌───┐┌───┐┌───┐
  │MCP││MCP││MCP││MCP││MCP│  ← Independent services
  │ 1 ││ 2 ││ 3 ││ 4 ││ 5 │
  └───┘└───┘└───┘└───┘└───┘
  Each has its own URL, scaling, lifecycle
```

---

## Why Separate Deployment Matters

### 1. Independent Scaling

Different components have different load patterns:

```
MCP Server (notes):     Low traffic, 10 req/min
MCP Server (search):    High traffic, 1000 req/min
Agent Backend:          Medium traffic, 100 req/min
```

Separate services = separate auto-scaling policies. You don't waste money scaling the notes server just because the search server is busy.

---

### 2. Independent Updates and Zero Downtime

```
Scenario: Fix a bug in the notes MCP server

Monolithic:
1. Build entire application
2. Deploy everything
3. All agents go down during deploy
4. Risk: might break unrelated components

Microservices:
1. Build only notes MCP server
2. Deploy only that service
3. Agents stay up, seamlessly switch to new server
4. Risk isolated to one service
```

---

### 3. Reusability Across Products

One MCP server, many consumers:

```
        Product A (chatbot)
              │
              ▼
        ┌──────────┐
        │  Notes   │
        │   MCP    │  ← One server, multiple consumers
        │  Server  │
        └──────────┘
              ▲
              │
        Product B (CLI tool)
              │
              ▼
        Product C (web app)
```

If notes MCP server were bundled with Product A, Products B and C would need to duplicate it or awkwardly depend on Product A's deployment.

---

### 4. Security Boundaries

Each service gets its own identity and permissions:

```
Notes MCP Server:
- Can read/write Cloud Storage bucket "notes-data"
- Cannot access user database
- Cannot send emails

Email MCP Server:
- Can access SendGrid API
- Cannot access Cloud Storage
- Cannot access user database

Agent Backend:
- Can call MCP servers
- Can read user database
- Cannot directly access Cloud Storage or SendGrid
```

Principle of least privilege enforced at the infrastructure level.

---

### 5. Fault Isolation

```
If Notes MCP Server crashes:
- Search MCP Server: ✅ Still running
- Calendar MCP Server: ✅ Still running  
- Agent Backend: ✅ Still running (just can't use notes)
- Impact: Notes features degraded, everything else works

vs.

If Monolith crashes:
- Everything: ❌ Down
- Impact: Complete outage
```

---

## Architecture Patterns

### Pattern 1: Simple Agent + Multiple MCP Servers

```
┌─────────────────────────────┐
│   Agent Backend (Cloud Run) │
│                             │
│   - FastAPI                 │
│   - LangGraph Agent         │
│   - MCP Clients             │
└─────────────┬───────────────┘
              │
       ┌──────┼──────┬──────┐
       │      │      │      │
       ▼      ▼      ▼      ▼
    ┌────┐ ┌────┐ ┌────┐ ┌────┐
    │MCP1│ │MCP2│ │MCP3│ │MCP4│
    └────┘ └────┘ └────┘ └────┘
```

**Best for:** Single agent, multiple tools, straightforward workflow

---

### Pattern 2: Multi-Agent with Shared MCP Servers

```
┌────────┐  ┌────────┐  ┌────────┐
│Agent A │  │Agent B │  │Agent C │
│Backend │  │Backend │  │Backend │
└───┬────┘  └───┬────┘  └───┬────┘
    │           │           │
    └───────────┼───────────┘
                │
         ┌──────┼──────┬──────┐
         │      │      │      │
         ▼      ▼      ▼      ▼
      ┌────┐ ┌────┐ ┌────┐ ┌────┐
      │MCP1│ │MCP2│ │MCP3│ │MCP4│
      └────┘ └────┘ └────┘ └────┘
```

**Best for:** Multiple agent products sharing common tools (notes, search, calendar)

---

### Pattern 3: Router Agent + Specialized Sub-Agents

```
        User Request
             │
             ▼
      ┌──────────────┐
      │Router Agent  │  ← Decides which agent to use
      └──────┬───────┘
             │
      ┌──────┼──────┬──────┐
      │      │      │      │
      ▼      ▼      ▼      ▼
   ┌────┐ ┌────┐ ┌────┐ ┌────┐
   │Agnt│ │Agnt│ │Agnt│ │Agnt│  ← Specialized agents
   │ A  │ │ B  │ │ C  │ │ D  │
   └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘
     │      │      │      │
     ▼      ▼      ▼      ▼
   ┌────┐ ┌────┐ ┌────┐ ┌────┐
   │MCP │ │MCP │ │MCP │ │MCP │  ← Each agent has its own MCP servers
   │ A  │ │ B  │ │ C  │ │ D  │
   └────┘ └────┘ └────┘ └────┘
```

**Best for:** Complex multi-agent systems with domain-specific tooling

---

## Deploying on Google Cloud Platform

### Service: Cloud Run (Recommended for Most Use Cases)

Cloud Run is a fully managed serverless platform perfect for MCP servers:
- Auto-scales to zero (pay only when used)
- Native HTTP/SSE support
- Container-based (bring any runtime)
- Simple deployment
- Built-in load balancing and TLS

---

### Deploying an MCP Server to Cloud Run

**Step 1: Prepare your MCP server**

```dockerfile
# Dockerfile
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY . .

RUN uv sync

EXPOSE 8080

CMD ["uv", "run", "python", "server.py"]
```

**Step 2: Update server to use PORT environment variable**

Cloud Run assigns a dynamic port via the `PORT` env var:

```python
# server.py
import os
import uvicorn
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notes-server")

@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Add a new note."""
    # implementation
    return f"✅ Note '{title}' saved."

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=port)
```

**Step 3: Deploy**

```bash
# Authenticate
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Deploy MCP server
gcloud run deploy notes-mcp-server \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 10

# Output:
# Service URL: https://notes-mcp-server-xyz-uc.a.run.app
```

**Step 4: Test the deployment**

```bash
# Health check
curl https://notes-mcp-server-xyz-uc.a.run.app/health

# Connect from your agent
client = MultiServerMCPClient({
    "notes": {
        "url": "https://notes-mcp-server-xyz-uc.a.run.app/sse",
        "transport": "sse"
    }
})
```

---

### Deploying the Agent Backend to Cloud Run

```bash
# backend/main.py - update to use PORT
import os
port = int(os.getenv("PORT", "8001"))
uvicorn.run("backend.main:app", host="0.0.0.0", port=port)

# Deploy
gcloud run deploy agent-backend \
  --source backend/ \
  --region us-central1 \
  --set-env-vars "MCP_SERVER_URL=https://notes-mcp-server-xyz-uc.a.run.app" \
  --set-secrets "OPENAI_API_KEY=openai-key:latest" \
  --memory 1Gi \
  --cpu 2 \
  --max-instances 20
```

---

### Deploying the Frontend to Cloud Run

```bash
# frontend/app.py - Streamlit config
# Create a .streamlit/config.toml
[server]
port = 8080
address = "0.0.0.0"
headless = true

# Deploy
gcloud run deploy agent-frontend \
  --source frontend/ \
  --region us-central1 \
  --set-env-vars "BACKEND_URL=https://agent-backend-xyz-uc.a.run.app" \
  --memory 512Mi
```

---

### Using Cloud Storage Instead of notes.json

In production, replace the JSON file with Cloud Storage:

```python
from google.cloud import storage

BUCKET_NAME = os.getenv("GCS_BUCKET", "mcp-notes-data")

def load_notes() -> dict:
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("notes.json")
    
    if not blob.exists():
        return {}
    
    return json.loads(blob.download_as_string())

def save_notes(notes: dict):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("notes.json")
    blob.upload_from_string(json.dumps(notes, indent=2))
```

Grant the Cloud Run service account storage permissions:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:notes-mcp-server@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

---

## Deploying on AWS

### Service: AWS Fargate with ALB

Fargate is AWS's serverless container platform, similar to Cloud Run:

**Step 1: Push image to ECR**

```bash
# Create ECR repository
aws ecr create-repository --repository-name notes-mcp-server

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t notes-mcp-server .
docker tag notes-mcp-server:latest \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/notes-mcp-server:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/notes-mcp-server:latest
```

**Step 2: Create ECS Fargate task definition**

```json
{
  "family": "notes-mcp-server",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "notes-mcp-server",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/notes-mcp-server:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "PORT",
          "value": "8080"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:openai-key"
        }
      ]
    }
  ]
}
```

**Step 3: Create ECS service with ALB**

```bash
aws ecs create-service \
  --cluster mcp-cluster \
  --service-name notes-mcp-server \
  --task-definition notes-mcp-server \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=notes-mcp-server,containerPort=8080"
```

**Use S3 instead of notes.json:**

```python
import boto3

s3 = boto3.client('s3')
BUCKET = os.getenv("S3_BUCKET", "mcp-notes-data")

def load_notes():
    try:
        obj = s3.get_object(Bucket=BUCKET, Key="notes.json")
        return json.loads(obj['Body'].read())
    except s3.exceptions.NoSuchKey:
        return {}

def save_notes(notes):
    s3.put_object(
        Bucket=BUCKET,
        Key="notes.json",
        Body=json.dumps(notes, indent=2)
    )
```

---

## Deploying on Azure

### Service: Azure Container Apps

Similar to Cloud Run and Fargate:

**Step 1: Create Container Registry**

```bash
az acr create \
  --resource-group mcp-resources \
  --name mcpregistry \
  --sku Basic

az acr login --name mcpregistry
```

**Step 2: Build and push**

```bash
docker build -t notes-mcp-server .
docker tag notes-mcp-server mcpregistry.azurecr.io/notes-mcp-server:latest
docker push mcpregistry.azurecr.io/notes-mcp-server:latest
```

**Step 3: Deploy to Container Apps**

```bash
az containerapp create \
  --name notes-mcp-server \
  --resource-group mcp-resources \
  --environment mcp-env \
  --image mcpregistry.azurecr.io/notes-mcp-server:latest \
  --target-port 8080 \
  --ingress external \
  --registry-server mcpregistry.azurecr.io \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 0 \
  --max-replicas 10
```

**Use Azure Blob Storage:**

```python
from azure.storage.blob import BlobServiceClient

connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
blob_service = BlobServiceClient.from_connection_string(connection_string)
container = blob_service.get_container_client("mcp-notes")

def load_notes():
    try:
        blob_client = container.get_blob_client("notes.json")
        return json.loads(blob_client.download_blob().readall())
    except:
        return {}

def save_notes(notes):
    blob_client = container.get_blob_client("notes.json")
    blob_client.upload_blob(
        json.dumps(notes, indent=2),
        overwrite=True
    )
```

---

## Kubernetes Deployment

For organizations already on Kubernetes (GKE, EKS, AKS):

**Deployment manifest for MCP server:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: notes-mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: notes-mcp-server
  template:
    metadata:
      labels:
        app: notes-mcp-server
    spec:
      containers:
      - name: server
        image: gcr.io/PROJECT/notes-mcp-server:latest
        ports:
        - containerPort: 8080
        env:
        - name: PORT
          value: "8080"
        - name: GCS_BUCKET
          value: "mcp-notes-data"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: notes-mcp-server
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: notes-mcp-server
```

Apply:

```bash
kubectl apply -f notes-mcp-server.yaml
kubectl get service notes-mcp-server  # Get external IP
```

---

## Building MCP Servers for Cloud Services

### Pattern: MCP Server as Cloud SDK Wrapper

Build thin MCP wrappers around official cloud SDKs:

**Google Cloud Storage MCP Server:**

```python
from mcp.server.fastmcp import FastMCP
from google.cloud import storage
import os

mcp = FastMCP("gcs-server")

@mcp.tool()
def upload_file(bucket: str, filename: str, content: str) -> str:
    """Upload a file to Google Cloud Storage."""
    client = storage.Client()
    bucket_obj = client.bucket(bucket)
    blob = bucket_obj.blob(filename)
    blob.upload_from_string(content)
    return f"✅ Uploaded {filename} to gs://{bucket}/{filename}"

@mcp.tool()
def download_file(bucket: str, filename: str) -> str:
    """Download a file from Google Cloud Storage."""
    client = storage.Client()
    bucket_obj = client.bucket(bucket)
    blob = bucket_obj.blob(filename)
    
    if not blob.exists():
        return f"❌ File {filename} not found in bucket {bucket}"
    
    return blob.download_as_text()

@mcp.tool()
def list_files(bucket: str, prefix: str = "") -> str:
    """List files in a GCS bucket with optional prefix."""
    client = storage.Client()
    bucket_obj = client.bucket(bucket)
    blobs = bucket_obj.list_blobs(prefix=prefix)
    
    files = [blob.name for blob in blobs]
    if not files:
        return f"📭 No files found in gs://{bucket}/{prefix}"
    
    return f"📁 Files in gs://{bucket}/{prefix}:\n" + "\n".join(f"  - {f}" for f in files)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=port)
```

Deploy this as its own Cloud Run service. Now any agent can use GCS without importing the GCS SDK.

---

### Pattern: MCP Server for Third-Party APIs

Wrap external APIs (Slack, GitHub, etc.) as MCP servers:

**Slack MCP Server:**

```python
from mcp.server.fastmcp import FastMCP
from slack_sdk import WebClient
import os

mcp = FastMCP("slack-server")
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

@mcp.tool()
def send_message(channel: str, text: str) -> str:
    """Send a message to a Slack channel."""
    response = slack_client.chat_postMessage(
        channel=channel,
        text=text
    )
    return f"✅ Message sent to #{channel}"

@mcp.tool()
def list_channels() -> str:
    """List all Slack channels."""
    response = slack_client.conversations_list()
    channels = [c['name'] for c in response['channels']]
    return "Channels:\n" + "\n".join(f"  - #{c}" for c in channels)
```

---

## Environment Configuration

### Local Development (.env file)

```env
# .env (not committed)
OPENAI_API_KEY=sk-...
MCP_SERVER_URL=http://localhost:8000
```

### Production (Cloud Secrets)

**Google Cloud:**

```bash
# Store secret
echo -n "sk-..." | gcloud secrets create openai-key --data-file=-

# Grant access
gcloud secrets add-iam-policy-binding openai-key \
  --member="serviceAccount:agent-backend@PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Use in Cloud Run
gcloud run deploy agent-backend \
  --set-secrets="OPENAI_API_KEY=openai-key:latest"
```

**AWS:**

```bash
# Store secret
aws secretsmanager create-secret \
  --name openai-key \
  --secret-string "sk-..."

# Use in ECS task definition (JSON)
"secrets": [
  {
    "name": "OPENAI_API_KEY",
    "valueFrom": "arn:aws:secretsmanager:region:account:secret:openai-key"
  }
]
```

---

## Security Best Practices

### 1. Principle of Least Privilege

Each service gets only the permissions it needs:

```
Notes MCP Server IAM Policy:
✅ storage.objects.create on bucket "notes-data"
✅ storage.objects.get on bucket "notes-data"
❌ No access to databases
❌ No access to other buckets
❌ No access to secrets (except its own config)
```

### 2. Authentication Between Services

**Option A: Service-to-Service Auth (Recommended)**

Cloud providers have native identity systems:

```python
# Google Cloud - uses default credentials automatically
from google.cloud import storage
client = storage.Client()  # Auth handled via service account
```

**Option B: API Keys in Headers**

For non-cloud services, use API keys validated on the server:

```python
# MCP Server
from fastapi import Header, HTTPException

API_KEY = os.getenv("MCP_API_KEY")

async def verify_api_key(x_api_key: str = Header()):
    if x_api_key != API_KEY:
        raise HTTPException(401, "Invalid API key")

app.add_middleware(verify_api_key)
```

```python
# Agent Client
import httpx

client = httpx.Client(headers={"X-API-Key": os.getenv("MCP_API_KEY")})
```

### 3. Network Security

**VPC / Private Networking:**

Keep MCP servers on private networks if they don't need public internet access:

```bash
# GCP - deploy to VPC with no public ingress
gcloud run deploy notes-mcp-server \
  --ingress internal \
  --vpc-connector my-vpc-connector
```

**Firewall Rules:**

Only allow traffic from known sources (your agent services).

### 4. Rate Limiting

Protect MCP servers from abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/sse")
@limiter.limit("100/minute")
async def sse_endpoint():
    return mcp.sse_app()
```

---

## Monitoring and Observability

### Logging

**Structured logging for MCP servers:**

```python
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@mcp.tool()
def add_note(title: str, content: str) -> str:
    logger.info(json.dumps({
        "event": "tool_call",
        "tool": "add_note",
        "title": title,
        "content_length": len(content)
    }))
    # implementation
    logger.info(json.dumps({
        "event": "tool_success",
        "tool": "add_note",
        "title": title
    }))
    return f"✅ Note saved"
```

Logs flow to cloud logging automatically (Cloud Logging, CloudWatch, etc.).

### Metrics

Track key metrics:

```python
from prometheus_client import Counter, Histogram
import time

tool_calls = Counter('mcp_tool_calls_total', 'Total tool calls', ['tool_name'])
tool_duration = Histogram('mcp_tool_duration_seconds', 'Tool execution time', ['tool_name'])

@mcp.tool()
def add_note(title: str, content: str) -> str:
    tool_calls.labels(tool_name='add_note').inc()
    
    start = time.time()
    # implementation
    duration = time.time() - start
    
    tool_duration.labels(tool_name='add_note').observe(duration)
    return "✅ Note saved"
```

### Health Checks

Always add a health endpoint:

```python
from fastapi import FastAPI

app = FastAPI()
app.mount("/", mcp.sse_app())

@app.get("/health")
def health():
    # Check dependencies (database, storage, etc.)
    try:
        # Test storage access
        client = storage.Client()
        client.bucket("notes-data").exists()
        
        return {
            "status": "healthy",
            "service": "notes-mcp-server",
            "dependencies": {
                "gcs": "ok"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 503
```

---

## Scaling Considerations

### Auto-Scaling Configuration

**Cloud Run (GCP):**

```bash
gcloud run deploy notes-mcp-server \
  --min-instances 1 \        # Always keep 1 warm instance
  --max-instances 100 \      # Scale up to 100
  --cpu-throttling \         # Throttle CPU when idle (save cost)
  --concurrency 80           # 80 requests per instance
```

**Fargate (AWS) with Auto Scaling:**

```bash
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/mcp-cluster/notes-mcp-server \
  --min-capacity 2 \
  --max-capacity 50

aws application-autoscaling put-scaling-policy \
  --policy-name mcp-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/mcp-cluster/notes-mcp-server \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    "TargetValue=70.0,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization}"
```

### Connection Pooling

For MCP clients connecting to multiple servers:

```python
import httpx

# Create a persistent session with connection pooling
session = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    timeout=60.0
)

client = MultiServerMCPClient(
    {
        "notes": {"url": "https://notes-server...", "transport": "sse"},
        "gcs": {"url": "https://gcs-server...", "transport": "sse"}
    },
    http_client=session  # Reuse connections across servers
)
```

---

## CI/CD Pipeline

**Example GitHub Actions workflow:**

```yaml
# .github/workflows/deploy-mcp-server.yml
name: Deploy Notes MCP Server

on:
  push:
    branches: [main]
    paths:
      - 'mcp_server/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy notes-mcp-server \
            --source mcp_server/ \
            --region us-central1 \
            --project ${{ secrets.GCP_PROJECT_ID }}
```

**Example GitLab CI:**

```yaml
# .gitlab-ci.yml
deploy-mcp-server:
  stage: deploy
  image: google/cloud-sdk:alpine
  script:
    - echo $GCP_SA_KEY | base64 -d > ${HOME}/gcloud-service-key.json
    - gcloud auth activate-service-account --key-file ${HOME}/gcloud-service-key.json
    - gcloud config set project $GCP_PROJECT_ID
    - gcloud run deploy notes-mcp-server --source mcp_server/ --region us-central1
  only:
    - main
  changes:
    - mcp_server/**
```

---

## Cost Optimization

### Strategy 1: Scale to Zero

For low-traffic MCP servers, use serverless platforms that scale to zero:

```bash
# Cloud Run - pay only when requests are being processed
gcloud run deploy notes-mcp-server \
  --min-instances 0  # Scale to zero when idle
```

Cost: $0/month when unused, pay per 100ms of CPU + memory when active.

### Strategy 2: Right-Size Resources

Don't over-provision. Start small:

```bash
# Start with minimal resources
--memory 256Mi --cpu 1

# Monitor usage, scale up only if needed
--memory 512Mi --cpu 1
```

### Strategy 3: Share MCP Servers Across Products

One notes MCP server used by 5 different agent products = 1/5 the cost per product.

### Strategy 4: Use Spot/Preemptible Instances

For non-critical MCP servers (dev/staging), use cheaper compute:

```bash
# GKE - use spot nodes
gcloud container node-pools create spot-pool \
  --cluster mcp-cluster \
  --spot
```

### Cost Monitoring

Set up budget alerts:

```bash
# GCP - alert when spending exceeds $100/month
gcloud billing budgets create \
  --billing-account BILLING_ACCOUNT_ID \
  --display-name "MCP Infrastructure Budget" \
  --budget-amount 100 \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90
```

---

## Production Checklist

Before going live, verify:

```
Infrastructure:
☐ Each MCP server is a separate service
☐ Agent backend is a separate service
☐ All services can reach each other
☐ Load balancer/ingress configured
☐ SSL/TLS certificates valid
☐ DNS records pointing to services

Security:
☐ API keys in secret manager (not .env files)
☐ IAM roles follow least privilege
☐ Network policies restrict traffic
☐ Rate limiting enabled
☐ Input validation on all tools
☐ Output sanitization for LLM safety

Observability:
☐ Structured logging enabled
☐ Metrics collection configured
☐ Health check endpoints working
☐ Alerts set up for failures
☐ Dashboards created

Reliability:
☐ Auto-scaling configured
☐ Multiple replicas for HA
☐ Graceful shutdown handling
☐ Retry logic in MCP clients
☐ Circuit breakers for failing servers
☐ Backup/restore plan for data

Performance:
☐ Connection pooling enabled
☐ Caching where appropriate
☐ Resource limits set correctly
☐ Load testing completed

Cost:
☐ Budget alerts configured
☐ Resources right-sized
☐ Scale-to-zero enabled where possible
☐ Unused resources cleaned up

Compliance:
☐ Data residency requirements met
☐ Audit logging enabled
☐ Sensitive data encrypted at rest
☐ PII handling compliant with regulations
```

---

## Summary: The Deployment Principles

1. **Separate services** — MCP servers independent from agents
2. **Use managed platforms** — Cloud Run, Fargate, Container Apps
3. **Secrets in secret managers** — Never hardcode credentials
4. **Least privilege IAM** — Each service gets minimum needed permissions
5. **Monitor everything** — Logs, metrics, health checks, alerts
6. **Scale appropriately** — Auto-scale based on load
7. **Secure the perimeter** — API keys, rate limits, private networks
8. **Plan for failure** — Retry logic, circuit breakers, graceful degradation

Follow these principles and your MCP infrastructure will be production-ready, secure, scalable, and maintainable.

---

*This guide reflects production deployment patterns as of early 2026. Always consult your cloud provider's latest documentation for platform-specific updates.*