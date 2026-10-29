#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " Predictive Autoscaler Environment Setup (Linux / macOS)  "
echo "=========================================================="

if command -v uv &> /dev/null; then
    echo "[1/4] Found Astral uv package manager."
    uv venv --python 3.11 .venv
    uv pip install -r requirements.txt --python .venv/bin/python
elif command -v python3 &> /dev/null; then
    echo "[1/4] Found Python3. Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    echo "[ERROR] Neither uv nor python3 was found on PATH."
    exit 1
fi

echo "[2/4] Generating synthetic benchmark workloads..."
.venv/bin/python workloads/workload_generator.py --output-dir ./data/sample

echo "[3/4] Training Prophet and LSTM models..."
.venv/bin/python scripts/train_model.py

echo "[4/4] Executing test suite..."
.venv/bin/python -m pytest tests/ -v

echo "=========================================================="
echo " Setup complete! To start locally, run: ./scripts/start_local.sh"
echo "=========================================================="
