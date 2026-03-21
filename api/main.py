"""FastAPI application — Development Factor LGD Backtesting."""

import sys
from pathlib import Path

# Ensure src/ is on path for lgd_model imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.models import ConfigDefaultsResponse
from api.routers import analysis, download, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup on shutdown
    from api.services.file_store import cleanup_expired
    cleanup_expired()


app = FastAPI(
    title="Development Factor LGD Backtesting",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(upload.router)
app.include_router(analysis.router)
app.include_router(download.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config/defaults", response_model=ConfigDefaultsResponse)
async def config_defaults():
    return ConfigDefaultsResponse(
        discount_rate=0.15,
        window_sizes=[12, 18, 24, 30, 36, 42, 48, 54, 60],
        ci_percentile=0.75,
        max_tid=60,
    )


# Serve React build in production (must be last — catches all non-API routes)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="spa")


def run():
    """CLI entry point: lgd-server."""
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
