"""PaperTrail FastAPI application entry point.

Phase 1: a minimal app exposing GET /api/health with CORS enabled for the
Next.js frontend running on http://localhost:3000. Routers and database
wiring are added in later phases.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PaperTrail API", version="0.1.0")

# Allow the Next.js dev server (localhost:3000) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """Liveness probe used by the frontend and by our own verification steps."""
    return {"status": "ok"}
