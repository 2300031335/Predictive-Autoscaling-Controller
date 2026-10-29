#!/usr/bin/env bash
echo "Starting Predictive Autoscaler Service on http://127.0.0.1:8000..."
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
