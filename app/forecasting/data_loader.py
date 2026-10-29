"""Data loading, provenance tracking, and validation for time-series traces."""
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from app.schemas import MetricPoint

logger = logging.getLogger(__name__)


class TraceDataLoader:
    """Loads, validates, and prepares historical trace data with strict provenance."""

    def __init__(self, raw_dir: Union[str, Path] = "./data/raw"):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_trace_hash(df: pd.DataFrame) -> str:
        """Computes deterministic SHA256 checksum of raw trace data."""
        data_str = df.to_json(orient="records", date_format="iso")
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    def load_from_points(self, points: List[MetricPoint]) -> Tuple[pd.DataFrame, Dict[str, any]]:
        """Converts list of MetricPoint Pydantic models to a validated DataFrame."""
        if not points:
            raise ValueError("Input points list cannot be empty.")

        records = [
            {
                "timestamp": p.timestamp,
                "requests_per_second": float(p.requests_per_second),
                "latency_ms": p.latency_ms,
                "cpu_utilization": p.cpu_utilization,
                "memory_utilization": p.memory_utilization,
                "current_replicas": p.current_replicas,
                "error_rate": p.error_rate,
            }
            for p in points
        ]
        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        metadata = {
            "record_count": len(df),
            "start_time": df["timestamp"].min().isoformat(),
            "end_time": df["timestamp"].max().isoformat(),
            "provenance_hash": self.compute_trace_hash(df),
        }
        return df, metadata

    def load_from_csv(self, file_path: Union[str, Path]) -> Tuple[pd.DataFrame, Dict[str, any]]:
        """Loads and verifies a CSV trace file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Trace file not found: {file_path}")

        df = pd.read_csv(path)
        if "timestamp" not in df.columns or "requests_per_second" not in df.columns:
            raise ValueError("CSV must contain 'timestamp' and 'requests_per_second' columns.")

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        metadata = {
            "source_file": str(path.resolve()),
            "record_count": len(df),
            "start_time": df["timestamp"].min().isoformat(),
            "end_time": df["timestamp"].max().isoformat(),
            "provenance_hash": self.compute_trace_hash(df),
        }
        return df, metadata

    def save_raw_trace(self, df: pd.DataFrame, filename: str) -> Path:
        """Saves unmodified raw trace to raw directory preserving provenance."""
        target_path = self.raw_dir / filename
        df.to_csv(target_path, index=False)
        logger.info("Saved raw trace to %s (records: %d)", target_path, len(df))
        return target_path

    @staticmethod
    def chronological_split(
        df: pd.DataFrame, train_ratio: float = 0.80
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Strictly chronological train/test split preventing future data leakage."""
        if not (0.1 <= train_ratio <= 0.95):
            raise ValueError(f"train_ratio must be between 0.1 and 0.95, got {train_ratio}")

        time_col = "timestamp" if "timestamp" in df.columns else ("ds" if "ds" in df.columns else None)
        if time_col is not None:
            df_sorted = df.sort_values(time_col).reset_index(drop=True)
        else:
            df_sorted = df.reset_index(drop=True)

        split_idx = int(len(df_sorted) * train_ratio)
        if split_idx == 0 or split_idx >= len(df_sorted):
            raise ValueError("Data insufficient to create train and test splits.")

        train_df = df_sorted.iloc[:split_idx].copy().reset_index(drop=True)
        test_df = df_sorted.iloc[split_idx:].copy().reset_index(drop=True)

        logger.info(
            "Chronological split completed: train=%d records, test=%d records",
            len(train_df),
            len(test_df),
        )
        return train_df, test_df
