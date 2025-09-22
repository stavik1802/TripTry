

# app/server.py
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env when running locally
load_dotenv()

# ---- your system imports ----
from app.core.advanced_multi_agent_system import AdvancedMultiAgentSystem  
from app.database.mongo_store import MongoStore  

# -------------------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------------------
app = FastAPI(title="TripPlanner Multi-Agent Backend", version="1.1.0")

# -------------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite
        "http://127.0.0.1:5173",
        "http://localhost:3000",   # CRA
        "http://localhost:4173",   # Vite preview
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------------
# System init
# -------------------------------------------------------------------------
SLA_SECONDS = 300
system = AdvancedMultiAgentSystem(sla_seconds=SLA_SECONDS)
store = MongoStore()

# -------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------
class ProcessRequest(BaseModel):
    user_request: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class ProcessResponse(BaseModel):
    status: str
    response: Dict[str, Any]
    session_id: Optional[str] = None
    agents_used: Optional[List[str]] = None
    learning_insights: Optional[Dict[str, Any]] = None

# -------------------------------------------------------------------------
# API ROUTES FIRST (so they don't get shadowed by SPA catch-all)
# -------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}

@app.get("/health/db")
def db_health():
    try:
        store.client.admin.command("ping")
        probe = {"_type": "health_probe", "ts": datetime.utcnow()}
        ins = store.runs.insert_one(probe)
        ok = store.runs.find_one({"_id": ins.inserted_id}, {"_id": 1}) is not None
        return {"ok": True, "read_back": ok}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/_debug/memory_counts")
def memory_counts():
    try:
        from app.agents.utils.memory_system import MemorySystem  # lazy import
        ms = MemorySystem()
        db = ms.db
        if not db:
            return {"memories": -1, "learning_metrics": -1, "user_preferences": -1}
        return {
            "memories": db.memories.count_documents({}),
            "learning_metrics": db.learning_metrics.count_documents({}),
            "user_preferences": db.user_preferences.count_documents({}),
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/runs/latest")
def runs_latest(limit: int = 10):
    try:
        items = store.latest(limit=limit)
        for it in items:
            it["_id"] = str(it["_id"])
        return {"ok": True, "items": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/process", response_model=ProcessResponse)
def process(req: ProcessRequest):
    context = {
        "countries": [],
        "cities": [],
        "dates": {},
        "travelers": {},
        "preferences": {},
        "budget_caps": {},
        "target_currency": "USD",
    }
    intent = "plan_trip"

    session_id = req.session_id or req.user_id or "anonymous"
    run_id = store.start_run(
        session_id=session_id,
        user_query=req.user_request,
        intent=intent,
        context=context,
    )

    try:
        result = system.process_request(
            user_request=req.user_request,
            user_id=req.user_id,
            session_id=req.session_id,
        )

        if isinstance(result, dict) and "response" in result:
            final_payload = result["response"]
        elif isinstance(result, dict):
            final_payload = result
        else:
            final_payload = {"raw": str(result)}

        store.finish_run(run_id, final=final_payload, status="success")
        return result
    except Exception as e:
        store.finish_run(run_id, final={}, status="error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}") from e

# -------------------------------------------------------------------------
# Static frontend (Vite/React build) AFTER API
# -------------------------------------------------------------------------
DIST_DIR = Path(__file__).resolve().parents[2] / "trip_ui" / "dist"
ASSETS_DIR = DIST_DIR / "assets"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(DIST_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Keep API space clear (but API routes are already registered above)
        if full_path.startswith(("_debug", "api/")):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(str(DIST_DIR / "index.html"))
else:
    @app.get("/")
    def root_no_frontend():
        return {"message": "TripPlanner backend is alive (no frontend build found)."}
