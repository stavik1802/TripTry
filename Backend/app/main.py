# app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import os

# Your system
from agents.advanced_multi_agent_system import AdvancedMultiAgentSystem

# --------- Request/Response models ---------
class PlanRequest(BaseModel):
    query: str
    user_id: Optional[str] = "anonymous"
    context: Optional[Dict[str, Any]] = None

class PlanResponse(BaseModel):
    status: str
    response: Dict[str, Any]
    session_id: str
    agents_used: list
    learning_insights: Dict[str, Any]

# --------- App setup ---------
app = FastAPI(title="Trip Planner Backend", version="1.0.0")

# SLA can be injected via env if you want time-budgeted responses
SLA_SECONDS = float(os.getenv("SLA_SECONDS", "0") or 0) or None

# Instantiate once so agents/tools are re-used across requests
system = AdvancedMultiAgentSystem(sla_seconds=SLA_SECONDS)

@app.get("/healthz")
def health():
    return {"ok": True}

@app.post("/v1/plan", response_model=PlanResponse)
def plan(req: PlanRequest):
    try:
        result = system.process_request(
            user_request=req.query,
            user_id=req.user_id or "anonymous",
            context=req.context or {},
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result)
        return result  # matches PlanResponse fields
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
