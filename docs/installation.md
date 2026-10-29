# Installation and Operating Guide

## 1. Prerequisites

- **Operating System**: Windows 10/11, macOS, or Linux (Ubuntu 20.04+).
- **Python**: Version 3.11 recommended (pre-compiled Prophet wheels available).
- **Package Manager**: [Astral `uv`](https://github.com/astral-sh/uv) or standard `pip`.
- **Containers**: Docker Desktop / Docker Engine and Docker Compose (optional for local standalone mode).
- **Kubernetes**: `kind`, `minikube`, or any CNCF-compliant Kubernetes cluster.
- **KEDA**: KEDA Operator v2.10+ (if deploying to cluster).

---

## 2. Windows Setup (PowerShell)

Execute the automated setup script:
```powershell
# In PowerShell:
.\scripts\setup.ps1
```

Or run manual steps:
```powershell
# 1. Create Python 3.11 virtual environment with uv
uv venv --python 3.11 .venv

# 2. Install dependencies
uv pip install -r requirements.txt --python .venv\Scripts\python.exe

# 3. Generate benchmark traces
.\.venv\Scripts\python.exe workloads/workload_generator.py --output-dir ./data/sample

# 4. Train Prophet & LSTM models
.\.venv\Scripts\python.exe scripts/train_model.py

# 5. Run test suite
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

---

## 3. Linux / macOS Setup (Bash)

```bash
# Make setup script executable and run:
chmod +x scripts/setup.sh scripts/start_local.sh
./scripts/setup.sh
```

---

## 4. Running the Local API & Controller

```powershell
# Start local API service
.\scripts\start_local.ps1
```
The FastAPI documentation UI is accessible at:
- Swagger UI: `http://localhost:8000/docs`
- Prometheus Metrics: `http://localhost:8000/metrics`
- Health check: `http://localhost:8000/health`

---

## 5. Docker Compose Deployment

To run the complete stack (Controller, Sample App, Prometheus, Grafana) locally in containers:
```bash
docker compose up -d --build
```
- API & Controller: `http://localhost:8000`
- Sample App: `http://localhost:5678`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (User: `admin`, Pass: `admin`)

---

## 6. Kubernetes & KEDA Deployment

1. Create namespace:
```bash
kubectl apply -f kubernetes/namespace.yaml
```

2. Deploy sample app and predictive controller:
```bash
kubectl apply -f kubernetes/app-deployment.yaml
kubectl apply -f kubernetes/app-service.yaml
kubectl apply -f kubernetes/forecast-deployment.yaml
kubectl apply -f kubernetes/controller-deployment.yaml
```

3. To activate **Reactive HPA**:
```bash
kubectl apply -f kubernetes/reactive-hpa.yaml
```

4. To switch to **Predictive KEDA Scaling**:
```bash
# Remove reactive HPA to prevent controller collision
kubectl delete -f kubernetes/reactive-hpa.yaml

# Apply KEDA ScaledObject
kubectl apply -f kubernetes/keda-scaledobject.yaml
```
