"""
Root Application Launcher.

Starts the FastAPI backend server using Uvicorn.

Usage:
    python main.py
Or with uvicorn directly:
    uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""

import uvicorn
from src.email_automation.config import settings
from src.email_automation.api.app import app


if __name__ == "__main__":
    print(f"============================================================")
    print(f"Starting Email Automation & Reminder System API Server")
    print(f"Host: {settings.API_HOST}:{settings.API_PORT}")
    print(f"Delivery Mode: {'SIMULATION (Safe Dry Run)' if settings.DRY_RUN else 'LIVE SMTP'}")
    print(f"Interactive API Docs: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    print(f"============================================================")
    uvicorn.run(
        "src.email_automation.api.app:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
