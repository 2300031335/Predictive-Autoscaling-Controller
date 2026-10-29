"""Unit tests for Prophet forecasting engine."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import pytest

from app.forecasting.prophet_model import ProphetForecaster


def test_prophet_fit_and_predict(tmp_path):
    start = datetime(2026, 1, 1, 0, 0, 0)
    # Generate 30 sample points
    dates = [start + timedelta(minutes=i) for i in range(30)]
    y_values = [20.0 + 2.0 * i + (i % 3) for i in range(30)]

    df = pd.DataFrame({"ds": dates, "y": y_values})

    forecaster = ProphetForecaster(random_seed=42)
    forecaster.fit(df)
    assert forecaster.is_fitted is True

    predictions = forecaster.predict(horizon_minutes=5, interval_seconds=60)
    assert len(predictions) == 5

    for p in predictions:
        assert p.predicted_requests_per_second >= 0.0
        assert p.lower_bound <= p.predicted_requests_per_second <= p.upper_bound + 0.01

    # Test serialization
    model_file = tmp_path / "prophet_test.pkl"
    forecaster.save(model_file)
    assert model_file.exists()

    loaded = ProphetForecaster.load(model_file)
    assert loaded.is_fitted is True
    loaded_preds = loaded.predict(horizon_minutes=3, interval_seconds=60)
    assert len(loaded_preds) == 3


def test_prophet_insufficient_points_raises_error():
    df = pd.DataFrame(
        {
            "ds": [datetime(2026, 1, 1, 0, i, 0) for i in range(3)],
            "y": [10.0, 12.0, 14.0],
        }
    )
    forecaster = ProphetForecaster()
    with pytest.raises(ValueError) as exc:
        forecaster.fit(df)
    assert "Insufficient historical points" in str(exc.value)
