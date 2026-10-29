"""Service managing model lifecycles, forecasts, and cache."""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import numpy as np
import pandas as pd

from app.config import settings
from app.forecasting.data_loader import TraceDataLoader
from app.forecasting.preprocessing import TracePreprocessor
from app.forecasting.prophet_model import ProphetForecaster
from app.forecasting.lstm_model import LSTMForecaster
from app.schemas import ForecastPoint, ForecastRequest, ForecastResponse, MetricPoint

logger = logging.getLogger(__name__)


class ForecastService:
    """Manages forecasting pipelines, model caching, and forecast generation."""

    def __init__(self):
        self.prophet_forecaster = ProphetForecaster()
        self.lstm_forecaster = LSTMForecaster()
        self.preprocessor = TracePreprocessor(interval_seconds=settings.FORECAST_INTERVAL_SECONDS)
        self.loader = TraceDataLoader()
        self.latest_response: Optional[ForecastResponse] = None
        self.last_forecast_timestamp: Optional[datetime] = None

    def initialize_default_model(self, sample_csv: str = "./data/sample/workload_composite.csv"):
        """Initializes and trains the default baseline model using sample data if present."""
        path = Path(sample_csv)
        if path.exists():
            try:
                df_raw, _ = self.loader.load_from_csv(path)
                df_clean, _ = self.preprocessor.clean_and_resample(df_raw)
                df_prophet = self.preprocessor.to_prophet_dataframe(df_clean)
                self.prophet_forecaster.fit(df_prophet)
                logger.info("Initialized default Prophet model on %s", sample_csv)
            except Exception as e:
                logger.warning("Could not train initial model on %s: %s", sample_csv, e)

    def generate_forecast(self, req: ForecastRequest) -> ForecastResponse:
        """Processes request history, cleans data, fits model, and returns predictions."""
        # 1. Load from points
        df_raw, _ = self.loader.load_from_points(req.history)

        # 2. Preprocess & clean
        df_clean, _ = self.preprocessor.clean_and_resample(df_raw)
        df_prophet = self.preprocessor.to_prophet_dataframe(df_clean)

        # 3. Fit and predict based on configured model
        if settings.MODEL_TYPE.lower() == "lstm":
            forecaster = self.lstm_forecaster.fit(df_prophet)
            predictions = forecaster.predict(
                horizon_minutes=req.horizon_minutes,
                interval_seconds=req.interval_seconds,
            )
            model_type = "lstm"
        else:
            forecaster = self.prophet_forecaster.fit(df_prophet)
            predictions = forecaster.predict(
                horizon_minutes=req.horizon_minutes,
                interval_seconds=req.interval_seconds,
            )
            model_type = "prophet"

        pred_values = [p.predicted_requests_per_second for p in predictions]
        mean_rps = float(np.mean(pred_values)) if pred_values else 0.0
        max_rps = float(np.max(pred_values)) if pred_values else 0.0

        response = ForecastResponse(
            status="success",
            model_type=model_type,
            model_version="1.0.0",
            generated_at=datetime.now(timezone.utc),
            horizon_minutes=req.horizon_minutes,
            predictions=predictions,
            mean_predicted_rps=round(mean_rps, 2),
            max_predicted_rps=round(max_rps, 2),
        )

        self.latest_response = response
        self.last_forecast_timestamp = response.generated_at
        return response

    def get_latest_forecast(self) -> Optional[ForecastResponse]:
        """Returns the most recently computed forecast or None."""
        return self.latest_response


# Global singleton instance
forecast_service = ForecastService()
