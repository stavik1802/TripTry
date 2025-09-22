"""
Main FastAPI application entry point
"""
import uvicorn

# Import the app from server.py
from .server import app

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )