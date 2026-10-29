"""FastAPI application entrypoint exposing API, forecasting, metrics, controller, and web dashboard."""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.controller.scaling_policy import controller_engine
from app.metrics.exporter import MetricsExporter
from app.schemas import (
    ControllerStatus,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    KedaMetricResponse,
    ScalingDecision,
)
from app.services.forecast_service import forecast_service

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("predictive-autoscaler")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Predictive Autoscaler application (%s)...", settings.APP_NAME)
    # Attempt to initialize default model if sample data is available
    forecast_service.initialize_default_model("./data/sample/workload_composite.csv")
    yield
    logger.info("Shutting down Predictive Autoscaler application...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Predictive Autoscaling Controller with Prophet and LSTM Load Forecasting for Kubernetes / KEDA",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if directory exists
static_path = Path("static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


class ControllerEvaluationRequest(BaseModel):
    current_replicas: int = Field(default=1, ge=1)
    current_rps: float = Field(default=20.0, ge=0.0)
    predicted_rps: Optional[float] = Field(default=None, ge=0.0)
    metrics_age_seconds: Optional[float] = Field(default=5.0, ge=0.0)
    forecast_error_mape: Optional[float] = Field(default=5.0, ge=0.0)


@app.get("/", summary="Web Dashboard Frontend", response_class=HTMLResponse)
def index_frontend():
    """Serves the interactive web UI dashboard."""
    html_file = Path("static/index.html")
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse("<h1>Predictive Autoscaler API</h1><p>Visit <a href='/docs'>/docs</a> for Swagger UI.</p>")


@app.get("/dashboard", summary="Dashboard Alias", response_class=HTMLResponse)
def dashboard_frontend():
    return index_frontend()


@app.get("/api/info", summary="API Metadata")
def api_info():
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "endpoints": {
            "dashboard": "/",
            "health": "/health",
            "forecast": "/forecast",
            "latest_forecast": "/forecast/latest",
            "controller_status": "/controller/status",
            "metrics": "/metrics",
            "keda_metric": "/metrics/keda",
            "experiments_plot": "/experiments/plot",
            "experiments_summary": "/api/experiments/summary",
        },
    }


@app.get("/health", response_model=HealthResponse, summary="Health and readiness check")
def health():
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version="1.0.0",
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc),
        forecasting_ready=True,
        controller_ready=True,
    )


@app.post("/forecast", response_model=ForecastResponse, summary="Generate demand forecast")
def generate_forecast(req: ForecastRequest):
    try:
        response = forecast_service.generate_forecast(req)
        # Update exporter with predicted demand
        MetricsExporter.update_telemetry(
            incoming_rps=req.history[-1].requests_per_second if req.history else 0.0,
            predicted_rps=response.max_predicted_rps,
        )
        return response
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error in forecast data: {str(ve)}",
        )
    except Exception as e:
        logger.exception("Forecast generation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecast generation failed: {str(e)}",
        )


@app.get("/forecast/latest", response_model=ForecastResponse, summary="Get latest computed forecast")
def get_latest_forecast():
    latest = forecast_service.get_latest_forecast()
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast has been generated yet. Send a POST request to /forecast first.",
        )
    return latest


@app.get("/controller/status", response_model=ControllerStatus, summary="Get scaling controller status")
def get_controller_status():
    return controller_engine.get_status()


@app.post("/controller/evaluate", response_model=ScalingDecision, summary="Trigger scaling controller evaluation")
def evaluate_controller(req: ControllerEvaluationRequest):
    pred_rps = req.predicted_rps
    if pred_rps is None:
        latest = forecast_service.get_latest_forecast()
        pred_rps = latest.max_predicted_rps if latest else req.current_rps

    decision = controller_engine.evaluate(
        current_replicas=req.current_replicas,
        predicted_rps=pred_rps,
        current_rps=req.current_rps,
        metrics_age_seconds=req.metrics_age_seconds,
        forecast_error_mape=req.forecast_error_mape,
    )

    MetricsExporter.record_decision(
        action=decision.action.value,
        policy=decision.active_policy.value,
        is_fallback=decision.is_fallback,
    )
    MetricsExporter.update_telemetry(
        incoming_rps=req.current_rps,
        current_replicas=req.current_replicas,
        desired_replicas=decision.desired_replicas,
        predicted_rps=pred_rps,
        forecast_error=req.forecast_error_mape,
    )
    return decision


@app.get("/metrics/keda", response_model=KedaMetricResponse, summary="KEDA external metric scaler endpoint")
def get_keda_metric():
    """Returns desired replicas formatted for KEDA External Scaler."""
    status_obj = controller_engine.get_status()
    return KedaMetricResponse(
        metric_name="desired_replicas",
        value=status_obj.desired_replicas,
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/metrics", summary="Prometheus metrics exposition")
def metrics():
    """Exposes all Prometheus telemetry in standard format."""
    payload = MetricsExporter.generate_prometheus_payload()
    return Response(content=payload, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/experiments/plot", summary="Get Experiment Comparison Visualization PNG")
def get_experiment_plot():
    plot_file = Path("experiments/results/scaling_comparison_plot.png")
    if not plot_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment comparison plot not found. Run experiments/compare_results.py first.",
        )
    return FileResponse(plot_file, media_type="image/png")


@app.get("/api/experiments/summary", summary="Get Benchmark Summary JSON")
def get_experiment_summary():
    summary_file = Path("experiments/results/experiment_summary.json")
    if not summary_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment summary JSON not found. Run experiments/run_experiment.py first.",
        )
    with open(summary_file, "r") as f:
        data = json.load(f)
    return data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=(settings.APP_ENV == "development"),
    )
