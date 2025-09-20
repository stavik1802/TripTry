# app/server.py
import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---- your existing imports (agents, system, tools) ----
# Based on your logs: AdvancedMultiAgentSystem exists and registers agents.
from app.agents.advanced_multi_agent_system import AdvancedMultiAgentSystem  # noqa: E402

# ------------------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------------------
app = FastAPI(title="TripPlanner Multi-Agent Backend", version="1.0.0")

# ------------------------------------------------------------------------------
# CORS (ADD THIS)
# ------------------------------------------------------------------------------
# Allow your Vite dev server to call the API locally.
# For production, replace with your real UI origin, e.g. https://trip.yourdomain.com
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite (default)
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# System init (unchanged logic; just reading SLA from env if present)
# ------------------------------------------------------------------------------
SLA_SECONDS = int(os.getenv("SLA_SECONDS", "30"))
system = AdvancedMultiAgentSystem(sla_seconds=SLA_SECONDS)

# ------------------------------------------------------------------------------
# Models
# ------------------------------------------------------------------------------
class ProcessRequest(BaseModel):
    user_request: str
    user_id: Optional[str] = None

class ProcessResponse(BaseModel):
    status: str
    response: Dict[str, Any]
    session_id: Optional[str] = None
    agents_used: Optional[list[str]] = None
    learning_insights: Optional[Dict[str, Any]] = None

# ------------------------------------------------------------------------------
# Optional basic routes
# ------------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "TripPlanner backend is alive."}

@app.get("/health")
def health():
    return {"ok": True}

# Optional debug counts for Mongo (safe if MemorySystem is present)
@app.get("/_debug/memory_counts")
def memory_counts():
    try:
        # Import lazily to avoid circular imports if any
        from app.agents.memory_system import MemorySystem  # type: ignore
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

# ------------------------------------------------------------------------------
# /process endpoint
# ------------------------------------------------------------------------------
@app.post("/process", response_model=ProcessResponse)
def process(req: ProcessRequest):
    """
    Accepts:
      {
        "user_request": "restaurant recommendations in NYC",
        "user_id": "stav"   # optional
      }

    Returns (example):
      {
        "status": "success",
        "response": { ... your agents' output ... },
        "session_id": "session_2025....",
        "agents_used": [...],
        "learning_insights": {...}
      }
    """
    try:
        # ---- CALL YOUR EXISTING PIPELINE HERE ----
        # Your logs show this works already. Most common patterns:
        #   result = system.process_request(req.user_request, user_id=req.user_id)
        # OR result = system.handle_request({...})
        # OR result = system.run_pipeline({...})
        #
        # If your system already has a working /process route elsewhere,
        # you can keep that implementation. Otherwise, try:
        result = system.process_request(
            user_request=req.user_request,
            user_id=req.user_id,
        )
        # If your method signature differs, adjust the line above only.

        # Ensure the response matches the schema the UI expects
        if not isinstance(result, dict):
            raise RuntimeError("Pipeline returned a non-dict result.")
        if "status" not in result:
            result["status"] = "success"

        return result  # FastAPI will validate against ProcessResponse
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}") from e
