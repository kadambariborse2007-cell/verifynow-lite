"""
main.py - Starting point of the PAMAC VerifyNow backend.

Run with:  uvicorn main:app --reload --host 0.0.0.0 --port 8000

1. Creates the database tables (if they do not exist yet)
2. Adds all API routers under /api
3. Serves the frontend folder at "/" so the whole app runs from one command
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import models  # noqa: F401  (importing registers the tables with Base)
from database import Base, engine
from routes import auth_routes, report_routes, request_routes, verify_routes

# Create tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="PAMAC VerifyNow API")

# API routes (must be added BEFORE the static mount below)
app.include_router(auth_routes.router)
app.include_router(request_routes.router)
app.include_router(report_routes.router)
app.include_router(verify_routes.router)

# Serve frontend/ at http://localhost:8000/ (html=True makes "/" open index.html).
# Note: backend/uploads is deliberately NOT mounted - files go through protected endpoints.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
