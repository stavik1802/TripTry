from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime, timezone

from app.config import settings
from app.services.store import create_run, get_run
# from app.services.db import create_run, get_run

router = APIRouter()


def _to_iso(v):
    try:
        return v.isoformat()  # datetime/date objects
    except AttributeError:
        return str(v)         # strings or anything else

# -------- Request models --------
class CountryInput(BaseModel):
    name: str
    preferred_cities: List[str] = Field(default_factory=list)

class PlanRequest(BaseModel):
    countries: List[CountryInput]
    dates: Dict[str, str]  # {"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}
    travelers: Dict[str, int] = Field(default_factory=lambda: {"adults":1,"children":0})
    musts: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    budget_caps: Dict[str, float] = Field(default_factory=dict)
    target_currency: str = "EUR"
    passport_country: Optional[str] = None
    visa_notes: Optional[str] = None

class FreeTextRequest(BaseModel):
    query: str

# -------- Helpers --------
def _now():
    return datetime.now(timezone.utc)

def _serialize_run(doc: Dict[str, Any]) -> Dict[str, Any]:
    # Convert datetimes to ISO strings for JSON responses
    out = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in doc.items()}
    # Hide internal fields if needed
    return out

# -------- Endpoints --------
@router.post("/plan")
def create_plan(payload: Dict[str, Any] = Body(...)):
    """
    Accepts EITHER:
      - { "query": "<free text>" }
      - full PlanRequest JSON
    Persists run to Mongo with real run_id.
    """
    run_id = str(uuid4())

    if "query" in payload:
        try:
            req = FreeTextRequest(**payload)
        except ValidationError as e:
            raise HTTPException(400, f"Invalid free-text payload: {e}")
        mode = "free_text"
        request_obj = req.model_dump()
    else:
        try:
            req = PlanRequest(**payload)
        except ValidationError as e:
            raise HTTPException(400, f"Invalid structured payload: {e}")
        mode = "structured"
        request_obj = req.model_dump()

    doc = {
        "_id": run_id,
        "status": "pending",          # will become queued/running/done in Step 2+
        "mode": mode,
        "request": request_obj,
        "result": None,               # placeholder for itinerary
        "errors": [],
        "caps": {"steps": settings.step_cap, "cost_usd": settings.cost_cap_usd},
        "created_at": _now(),
        "updated_at": _now(),
    }
    create_run(doc)
    return {"run_id": run_id, "status": "pending"}

@router.get("/plan/{run_id}")
def get_plan_status(run_id: str):
    doc = get_run(run_id)
    if not doc:
        raise HTTPException(404, "run_id not found")
    # Return status + request; result is None for now (Step 2+ will populate)
    return {
        "run_id": run_id,
        "status": doc["status"],
        "request": doc["request"],
        "result": doc.get("result"),
        "created_at": _to_iso(doc.get("created_at")),
        "updated_at": _to_iso(doc.get("updated_at")),
    }
