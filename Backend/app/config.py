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
