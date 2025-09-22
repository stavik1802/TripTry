"""
Configuration Settings for TripPlanner Multi-Agent System

This module provides centralized configuration management for the TripPlanner
application, including environment variables, database settings, and system
parameters. It uses environment variables with sensible defaults for easy
deployment and configuration.

Key configuration areas:
- Application environment and port settings
- MongoDB connection and database configuration
- Default currency and cost cap settings
- Step limits for processing control

All settings can be overridden via environment variables for flexible
deployment across different environments.
"""

import os

class Settings:
    # App
    app_env: str = os.getenv("APP_ENV", "dev")
    port: int = int(os.getenv("PORT", "8080"))

    # Store / Mongo (used only if STORE_BACKEND=mongo)
    mongodb_uri: str = os.getenv("MONGODB_URI", "")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "trip_planner")

    # Planner caps (used by routes/plan.py when creating a run)
    default_currency: str = os.getenv("DEFAULT_CURRENCY", "EUR")
    cost_cap_usd: float = float(os.getenv("COST_CAP_USD", "8.0"))
    step_cap: int = int(os.getenv("STEP_CAP", "200"))

settings = Settings()
