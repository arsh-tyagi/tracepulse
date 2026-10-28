from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import logging

from backend.app.config import settings
from backend.app.database import init_db_engine
from backend.app.routers import health, monitors, internal, rules, metrics, sse

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("tracepulse.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing TracePulse database engine...")
    await init_db_engine()
    logger.info("TracePulse Control Plane successfully initialized.")
    yield
    logger.info("TracePulse shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="High-Throughput Synthetic API & Health Monitoring Engine Control Plane",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(monitors.router, prefix=settings.API_V1_PREFIX)
app.include_router(internal.router, prefix=settings.API_V1_PREFIX)
app.include_router(rules.router, prefix=settings.API_V1_PREFIX)
app.include_router(metrics.router, prefix=settings.API_V1_PREFIX)
app.include_router(sse.router, prefix=settings.API_V1_PREFIX)

# Static and Frontend files mounting
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "TracePulse API is running. Frontend index.html not yet present."}
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {"name": settings.APP_NAME, "status": "operational", "docs_url": "/docs"}
