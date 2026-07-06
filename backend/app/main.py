"""PaperTrail FastAPI application entry point.

Exposes GET /api/health, enables CORS for the Next.js frontend, and on
startup ensures the MySQL database and all tables exist. Routers are wired in
Phases 3-4.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers import documents

logger = logging.getLogger("papertrail")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the database + tables on startup if they don't exist yet."""
    try:
        init_db()
        logger.info("Database initialized (tables ensured).")
    except Exception as exc:  # noqa: BLE001 - keep the API up even if DB is down
        logger.warning("Database init skipped/failed: %s", exc)
    yield


app = FastAPI(title="PaperTrail API", version="0.1.0", lifespan=lifespan)

# Allow the Next.js dev server (localhost:3000) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(documents.router)


@app.get("/api/health")
def health():
    """Liveness probe used by the frontend and by our own verification steps."""
    return {"status": "ok"}
