"""
Metroika — Legal Metrology Compliance Checker
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import products, analysis, reports, dashboard, auth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("metroika")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("  METROIKA — Legal Metrology Compliance Checker")
    logger.info("  Starting up...")
    logger.info("=" * 60)

    # Create database tables
    await init_db()
    logger.info("Database initialized.")

    # Ensure directories exist
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload dir: {settings.upload_dir}")
    logger.info(f"Report dir: {settings.report_dir}")

    # Pre-warm Multilingual OCR engine in background thread so server starts instantly in <0.2s
    import asyncio
    from app.services.ocr import get_ocr_engine
    asyncio.create_task(asyncio.to_thread(get_ocr_engine))

    yield

    logger.info("Metroika shutting down.")


# Create the FastAPI app
app = FastAPI(
    title="Metroika",
    description=(
        "Legal Metrology Compliance Checker — "
        "Software System to check compliance of Packaged Commodities "
        "under Legal Metrology (Packaged Commodities) Rules, 2011"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(analysis.router)
app.include_router(reports.router)
app.include_router(dashboard.router)

# Mount static file directories for serving uploaded images and reports
app.mount(
    "/uploads",
    StaticFiles(directory=str(settings.upload_dir)),
    name="uploads",
)
app.mount(
    "/reports",
    StaticFiles(directory=str(settings.report_dir)),
    name="reports_static",
)


@app.get("/")
async def root():
    """Health check and API info."""
    return {
        "name": "Metroika",
        "version": "1.0.0",
        "description": "Legal Metrology Compliance Checker",
        "docs_url": "/docs",
        "status": "running",
    }


@app.get("/api/health")
async def health():
    """Health check endpoint with OCR engine readiness status."""
    from app.services.ocr import ocr_engine, get_ocr_status
    status_info = get_ocr_status()
    return {
        "status": "healthy",
        "ocr_ready": ocr_engine is not None and status_info.get("state") == "ready",
        "ocr_state": status_info.get("state", "ready" if ocr_engine is not None else "loading"),
        "ocr_message": status_info.get("message", "Ready"),
        "device": status_info.get("device", "gpu"),
    }
