"""Unit tests for TraceDataLoader and TracePreprocessor."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import pytest

from app.forecasting.data_loader import TraceDataLoader
from app.forecasting.preprocessing import TracePreprocessor
from app.schemas import MetricPoint


def test_load_from_points_and_provenance():
    loader = TraceDataLoader(raw_dir="./data/raw")
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    points = [
        MetricPoint(timestamp=now + timedelta(seconds=i * 10), requests_per_second=20.0 + i)
        for i in range(10)
    ]
    df, meta = loader.load_from_points(points)

    assert len(df) == 10
    assert "provenance_hash" in meta
    assert len(meta["provenance_hash"]) == 64  # SHA-256
    assert meta["record_count"] == 10


def test_chronological_split_no_leakage():
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    dates = [now + timedelta(minutes=i) for i in range(100)]
    df = pd.DataFrame(
        {
            "timestamp": dates,
            "requests_per_second": [10.0 + i for i in range(100)],
        }
    )

    train_df, test_df = TraceDataLoader.chronological_split(df, train_ratio=0.80)
    assert len(train_df) == 80
    assert len(test_df) == 20

    # Ensure strictly zero temporal leakage: max(train) < min(test)
    assert train_df["timestamp"].max() < test_df["timestamp"].min()


def test_preprocessor_resample_and_cleaning():
    preprocessor = TracePreprocessor(interval_seconds=60)
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # DataFrame with duplicates and gaps
    raw_df = pd.DataFrame(
        {
            "timestamp": [
                now,
                now,  # duplicate
                now + timedelta(seconds=60),
                now + timedelta(seconds=180),  # gap at 120
            ],
            "requests_per_second": [20.0, 30.0, 40.0, 50.0],
        }
    )

    cleaned_df, stats = preprocessor.clean_and_resample(raw_df)
    assert stats["duplicates_removed"] == 1
    assert stats["missing_points_interpolated"] >= 1
    assert len(cleaned_df) == 4  # 0s, 60s, 120s (filled), 180s

    prophet_df = preprocessor.to_prophet_dataframe(cleaned_df)
    assert list(prophet_df.columns) == ["ds", "y"]
    assert (prophet_df["y"] >= 0).all()
