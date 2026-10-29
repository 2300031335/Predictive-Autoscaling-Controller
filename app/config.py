"""Configuration settings for Predictive Autoscaling System."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Info
    APP_NAME: str = Field(default="Predictive Autoscaling Controller", description="Name of the service")
    APP_ENV: str = Field(default="development", description="Environment: development, test, production")
    APP_HOST: str = Field(default="0.0.0.0", description="Host to bind HTTP server")
    APP_PORT: int = Field(default=8000, description="Port to bind HTTP server")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Forecasting Configuration
    FORECAST_HORIZON_MINUTES: int = Field(default=5, description="Minutes ahead to forecast")
    FORECAST_INTERVAL_SECONDS: int = Field(default=60, description="Granularity interval in seconds")
    MODEL_TYPE: str = Field(default="prophet", description="Model type: prophet, lstm, or hybrid")
    MODEL_SAVE_PATH: str = Field(default="./data/processed/prophet_model.pkl", description="Path to persisted model")
    FALLBACK_MODEL_SAVE_PATH: str = Field(default="./data/processed/lstm_model.pt", description="Path to LSTM model")

    # Autoscaling Controller Policy Settings
    MIN_REPLICAS: int = Field(default=1, description="Minimum allowed replicas")
    MAX_REPLICAS: int = Field(default=10, description="Maximum allowed replicas")
    SAFE_CAPACITY_PER_REPLICA: float = Field(
        default=25.0, description="Safe maximum requests per second one replica can serve"
    )
    SAFETY_MARGIN_PERCENT: float = Field(
        default=0.15, description="Headroom buffer percentage (0.15 = 15%)"
    )
    MAX_SCALE_UP_RATE: int = Field(
        default=3, description="Maximum pods that can be added in a single scaling step"
    )
    MAX_SCALE_DOWN_RATE: int = Field(
        default=2, description="Maximum pods that can be removed in a single scaling step"
    )
    SCALE_UP_COOLDOWN_SECONDS: int = Field(
        default=60, description="Cooldown seconds after scale-up before another scale action"
    )
    SCALE_DOWN_COOLDOWN_SECONDS: int = Field(
        default=180, description="Cooldown seconds after scale-down before another scale action"
    )
    STALE_DATA_THRESHOLD_SECONDS: int = Field(
        default=120, description="Seconds without fresh metrics before entering fallback"
    )
    FORECAST_ERROR_FALLBACK_THRESHOLD: float = Field(
        default=0.35, description="Normalized MAPE/error threshold triggering reactive fallback"
    )

    # Reactive Baseline Settings
    REACTIVE_TARGET_CPU_UTILIZATION: float = Field(
        default=0.70, description="Reactive HPA target utilization (70%)"
    )

    # Kubernetes Cluster Target
    TARGET_DEPLOYMENT_NAME: str = Field(
        default="sample-app", description="Kubernetes Deployment name to scale"
    )
    TARGET_NAMESPACE: str = Field(
        default="predictive-system", description="Kubernetes Namespace"
    )


settings = Settings()
