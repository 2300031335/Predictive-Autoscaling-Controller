"""Prophet forecasting model wrapper with serialization and prediction bounds."""
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from prophet import Prophet

from app.schemas import ForecastPoint

logger = logging.getLogger(__name__)


class ProphetForecaster:
    """Production-grade Prophet forecasting engine for request load time series."""

    def __init__(
        self,
        interval_width: float = 0.80,
        changepoint_prior_scale: float = 0.05,
        daily_seasonality: bool = False,
        weekly_seasonality: bool = False,
        yearly_seasonality: bool = False,
        random_seed: int = 42,
    ):
        self.interval_width = interval_width
        self.changepoint_prior_scale = changepoint_prior_scale
        self.daily_seasonality = daily_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.yearly_seasonality = yearly_seasonality
        self.random_seed = random_seed
        self.model: Optional[Prophet] = None
        self.is_fitted: bool = False
        self.last_trained_at: Optional[datetime] = None
        self.training_metadata: Dict[str, any] = {}

    def _init_model(self) -> Prophet:
        # np.random.seed for reproducible Stan MCMC/optimization sampling
        np.random.seed(self.random_seed)
        return Prophet(
            interval_width=self.interval_width,
            changepoint_prior_scale=self.changepoint_prior_scale,
            daily_seasonality=self.daily_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            yearly_seasonality=self.yearly_seasonality,
            uncertainty_samples=100,
        )

    def fit(self, prophet_df: pd.DataFrame) -> "ProphetForecaster":
        """Fits the Prophet model on a dataframe with 'ds' (datetime) and 'y' (float)."""
        if len(prophet_df) < 5:
            raise ValueError(f"Insufficient historical points to fit Prophet. Got {len(prophet_df)}, minimum 5 required.")

        df = prophet_df.copy()
        df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)
        df["y"] = df["y"].astype(float).clip(lower=0.0)

        # Disable warnings in fitting
        logging.getLogger("cmdstanpy").setLevel(logging.ERROR)

        self.model = self._init_model()
        self.model.fit(df)
        self.is_fitted = True
        self.last_trained_at = datetime.utcnow()
        self.training_metadata = {
            "training_samples": len(df),
            "start_time": df["ds"].min().isoformat(),
            "end_time": df["ds"].max().isoformat(),
            "mean_rps": float(df["y"].mean()),
            "max_rps": float(df["y"].max()),
        }
        logger.info(
            "Prophet model successfully fitted on %d samples (%s to %s)",
            len(df),
            self.training_metadata["start_time"],
            self.training_metadata["end_time"],
        )
        return self

    def predict(
        self, horizon_minutes: int = 5, interval_seconds: int = 60
    ) -> List[ForecastPoint]:
        """Generates future predictions for the specified horizon and interval."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model has not been fitted yet. Call fit() before predict().")

        periods = max(1, int((horizon_minutes * 60) / interval_seconds))
        freq = f"{interval_seconds}s"

        future = self.model.make_future_dataframe(periods=periods, freq=freq, include_history=False)
        forecast = self.model.predict(future)

        forecast_points: List[ForecastPoint] = []
        for _, row in forecast.iterrows():
            # Demand cannot be negative: clamp predictions and uncertainty intervals to 0
            yhat = max(0.0, float(row["yhat"]))
            lower = max(0.0, float(row["yhat_lower"]))
            upper = max(yhat, float(row["yhat_upper"]))

            forecast_points.append(
                ForecastPoint(
                    timestamp=pd.to_datetime(row["ds"]).to_pydatetime(),
                    predicted_requests_per_second=round(yhat, 2),
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                )
            )

        return forecast_points

    def save(self, filepath: Union[str, Path]) -> Path:
        """Serializes the fitted forecaster to disk."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info("Prophet model serialized to %s", path)
        return path

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "ProphetForecaster":
        """Loads a serialized forecaster from disk."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        with open(path, "rb") as f:
            forecaster = pickle.load(f)
        logger.info("Prophet model loaded from %s", path)
        return forecaster
