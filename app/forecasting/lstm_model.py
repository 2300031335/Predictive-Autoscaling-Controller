"""PyTorch LSTM time-series forecaster for model comparison."""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler

from app.schemas import ForecastPoint

logger = logging.getLogger(__name__)


class LSTMNet(nn.Module):
    """Two-layer LSTM with linear output projection."""

    def __init__(self, input_dim: int = 1, hidden_dim: int = 32, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.1 if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        # Select output of the last time step
        pred = self.fc(out[:, -1, :])
        return pred


class LSTMForecaster:
    """LSTM-based time-series forecasting engine."""

    def __init__(
        self,
        lookback_window: int = 10,
        hidden_dim: int = 32,
        num_layers: int = 2,
        epochs: int = 40,
        learning_rate: float = 0.01,
        random_seed: int = 42,
    ):
        self.lookback_window = lookback_window
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.epochs = epochs
        self.lr = learning_rate
        self.random_seed = random_seed
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.net: Optional[LSTMNet] = None
        self.is_fitted: bool = False
        self.last_timestamps: List[datetime] = []
        self.last_sequence: np.ndarray = np.array([])

        torch.manual_seed(self.random_seed)
        np.random.seed(self.random_seed)

    def _create_sequences(
        self, data: np.ndarray
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        X, y = [], []
        for i in range(len(data) - self.lookback_window):
            X.append(data[i : i + self.lookback_window])
            y.append(data[i + self.lookback_window])
        return torch.tensor(np.array(X), dtype=torch.float32), torch.tensor(
            np.array(y), dtype=torch.float32
        )

    def fit(self, prophet_df: pd.DataFrame) -> "LSTMForecaster":
        """Fits the LSTM model on time series dataframe with 'ds' and 'y'."""
        if len(prophet_df) <= self.lookback_window + 5:
            raise ValueError(
                f"Insufficient points ({len(prophet_df)}) for LSTM lookback window ({self.lookback_window})."
            )

        df = prophet_df.sort_values("ds").reset_index(drop=True)
        raw_values = df["y"].values.reshape(-1, 1).astype(np.float32)

        # Scale data to [0, 1]
        scaled_values = self.scaler.fit_transform(raw_values)
        self.last_sequence = scaled_values[-self.lookback_window :]
        self.last_timestamps = list(pd.to_datetime(df["ds"]))

        X, y = self._create_sequences(scaled_values)

        self.net = LSTMNet(
            input_dim=1, hidden_dim=self.hidden_dim, num_layers=self.num_layers
        )
        optimizer = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        criterion = nn.MSELoss()

        self.net.train()
        for epoch in range(self.epochs):
            optimizer.zero_grad()
            preds = self.net(X)
            loss = criterion(preds, y)
            loss.backward()
            optimizer.step()

        self.is_fitted = True
        logger.info(
            "LSTM trained on %d sequences for %d epochs. Final Loss: %.6f",
            len(X),
            self.epochs,
            loss.item(),
        )
        return self

    def predict(
        self, horizon_minutes: int = 5, interval_seconds: int = 60
    ) -> List[ForecastPoint]:
        """Autoregressively predicts future points."""
        if not self.is_fitted or self.net is None:
            raise RuntimeError("LSTM model has not been fitted yet.")

        periods = max(1, int((horizon_minutes * 60) / interval_seconds))
        self.net.eval()

        current_seq = self.last_sequence.copy()  # shape (lookback, 1)
        predictions_scaled = []

        with torch.no_grad():
            for _ in range(periods):
                x_input = torch.tensor(
                    current_seq.reshape(1, self.lookback_window, 1), dtype=torch.float32
                )
                pred = self.net(x_input).item()
                predictions_scaled.append([pred])
                # Shift sequence window
                current_seq = np.vstack([current_seq[1:], [[pred]]])

        # Invert scaling
        preds_unscaled = self.scaler.inverse_transform(predictions_scaled).flatten()
        preds_unscaled = np.clip(preds_unscaled, a_min=0.0, a_max=None)

        # Build timestamps
        last_dt = self.last_timestamps[-1]
        future_points: List[ForecastPoint] = []
        for i, val in enumerate(preds_unscaled):
            dt = last_dt + timedelta(seconds=(i + 1) * interval_seconds)
            # Estimate pseudo-confidence interval around point estimate (+-10%)
            val_flt = round(float(val), 2)
            lower = round(max(0.0, val_flt * 0.90), 2)
            upper = round(val_flt * 1.10, 2)
            future_points.append(
                ForecastPoint(
                    timestamp=dt,
                    predicted_requests_per_second=val_flt,
                    lower_bound=lower,
                    upper_bound=upper,
                )
            )

        return future_points
