"""FastAPI entrypoint for BusinessInsight Agent."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_agent import router as agent_router
from app.api.routes_eval import router as eval_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_trace import router as trace_router
from app.config import get_settings
from app.schemas import HealthResponse

settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(
    title=settings.app_name,
    description=(
        "An intelligent attribution and decision agent system for ecommerce "
        "business analysis."
    ),
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.include_router(agent_router)
app.include_router(eval_router)
app.include_router(metrics_router)
app.include_router(trace_router)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the local frontend demo page."""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return a lightweight service health signal for runtime checks."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
    )
