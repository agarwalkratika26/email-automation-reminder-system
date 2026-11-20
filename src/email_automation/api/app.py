"""
FastAPI Application Entry Point.

Sets up application lifespan, CORS restricted strictly to the local Next.js
dashboard origins (with allow_credentials=False), and registers all API routes.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.email_automation.config import settings
from src.email_automation.storage.database import init_db
from src.email_automation.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events cleanly."""
    init_db()
    yield


def create_app() -> FastAPI:
    """Initializes and configures the FastAPI application instance."""
    app = FastAPI(
        title="Email Automation & Reminder System API",
        description=(
            "A local Python automation system for scheduling email campaigns, "
            "personalizing templates, managing reminders, and tracking delivery audit logs. "
            "Operates in safe Simulation Mode by default."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # Cross-Origin Resource Sharing (CORS) Configuration
    # Strictly restricted to local dashboard origins; credentials disabled as tokens/cookies are not used.
    allowed_origins = [
        f"http://localhost:{settings.FRONTEND_PORT}",
        f"http://127.0.0.1:{settings.FRONTEND_PORT}",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept"],
    )

    app.include_router(router)
    return app


app = create_app()
