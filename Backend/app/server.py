

# app/server.py
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
import json

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
    # expose run_id to downstream coordination for per-agent logging
    try:
        context["run_id"] = str(run_id)
    except Exception:
        context["run_id"] = run_id

    try:
        result = system.process_request(
            user_request=req.user_request,
            user_id=req.user_id,
            session_id=req.session_id,
            context=context,
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
# Export endpoints
# -------------------------------------------------------------------------

def _build_export_payload(run: Dict[str, Any], fmt: str) -> Dict[str, Any]:
    """Normalize and extract export payloads from a run document.
    Expected final structure may contain keys like json_report / markdown_report / html_report.
    Fallback to the raw final payload when specific format keys are missing.
    """
    final = run.get("final", {}) if isinstance(run, dict) else {}
    payload: Dict[str, Any] = {}
    if fmt == "json":
        # ensure it's JSON serializable
        payload["body_bytes"] = (json.dumps(final.get("json_report", final), ensure_ascii=False)).encode("utf-8")
        payload["content_type"] = "application/json; charset=utf-8"
        payload["ext"] = "json"
    elif fmt == "md":
        md = final.get("markdown_report") or final.get("md") or "# Trip Report\n\n(No markdown report available)"
        payload["body_bytes"] = md.encode("utf-8")
        payload["content_type"] = "text/markdown; charset=utf-8"
        payload["ext"] = "md"
    elif fmt == "html":
        html = final.get("html_report") or final.get("html") or "<html><body><h1>Trip Report</h1><p>No HTML report available.</p></body></html>"
        payload["body_bytes"] = html.encode("utf-8")
        payload["content_type"] = "text/html; charset=utf-8"
        payload["ext"] = "html"
    elif fmt == "pdf":
        # Try to render a simple PDF from available HTML/Markdown/text using reportlab (no heavy system deps)
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import cm
        except Exception as e:
            raise HTTPException(status_code=501, detail="PDF export requires 'reportlab' to be installed")

        # Prefer the generated response text, fall back to HTML/MD/JSON
        def _extract_response_text(payload: Dict[str, Any]) -> Optional[str]:
            if not isinstance(payload, dict):
                return None
            # common locations
            rt = payload.get("response_text")
            if isinstance(rt, str) and rt.strip():
                return rt.strip()
            resp = payload.get("response")
            if isinstance(resp, dict):
                rt = resp.get("response_text")
                if isinstance(rt, str) and rt.strip():
                    return rt.strip()
                # sometimes doubled nesting: response.response.response_text
                inner = resp.get("response")
                if isinstance(inner, dict):
                    rt = inner.get("response_text")
                    if isinstance(rt, str) and rt.strip():
                        return rt.strip()
            return None

        txt = _extract_response_text(final) if isinstance(final, dict) else None
        uq = run.get("user_query") if isinstance(run, dict) else None
        html = final.get("html_report") or final.get("html") if isinstance(final, dict) else None
        md = final.get("markdown_report") or final.get("md") if isinstance(final, dict) else None
        if html:
            # naive tag strip for now
            try:
                import re
                txt = re.sub("<[^>]+>", "", html)
            except Exception:
                txt = html
        elif not txt and md:
            txt = md
        if not txt:
            # fallback to JSON pretty
            txt = json.dumps(final.get("json_report", final), ensure_ascii=False, indent=2)

        # If we have both question and answer, compose as Q/A
        if isinstance(uq, str) and uq.strip() and isinstance(txt, str) and txt.strip():
            txt = f"Q: {uq.strip()}\nA: {txt.strip()}"

        # Render to PDF bytes
        from io import BytesIO
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        left_margin = 2 * cm
        top_margin = height - 2 * cm
        line_height = 0.6 * cm
        max_width = width - 4 * cm

        # Simple word wrap
        def wrap_text(s: str, max_chars: int = 100) -> list[str]:
            lines = []
            for raw in s.splitlines():
                line = raw.strip()
                while len(line) > max_chars:
                    cut = line.rfind(' ', 0, max_chars)
                    if cut == -1:
                        cut = max_chars
                    lines.append(line[:cut])
                    line = line[cut:].lstrip()
                lines.append(line)
            return lines

        # estimate max_chars based on page width (very rough)
        max_chars = 95
        for i, line in enumerate(wrap_text(txt, max_chars=max_chars)):
            y = top_margin - i * line_height
            if y < 2 * cm:
                c.showPage()
                y = top_margin
                i = 0
            c.drawString(left_margin, y, line[:400])  # defensive cap
        c.showPage()
        c.save()
        payload["body_bytes"] = buf.getvalue()
        payload["content_type"] = "application/pdf"
        payload["ext"] = "pdf"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use one of: json|md|html|pdf")
    return payload


@app.get("/trip/export/{run_id}")
def export_by_run(run_id: str, fmt: str = "json"):
    """Export a specific run by its id as json|md|html.
    Returns a downloadable file with proper content type and filename.
    """
    doc = store.get_run(run_id)
    if not doc or doc.get("status") != "success":
        raise HTTPException(status_code=404, detail="Run not found or not successful")
    try:
        p = _build_export_payload(doc, fmt)
        filename = f"trip_{str(doc.get('_id'))}.{p['ext']}"
        return Response(content=p["body_bytes"], media_type=p["content_type"], headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}") from e


@app.get("/trip/export")
def export_latest_by_session(session_id: str, fmt: str = "json", all_responses: bool = False):
    """Export the latest successful result for a given session_id as json|md|html|pdf.
    If all_responses=true and fmt=pdf, the PDF will include all response_text entries from the session (one per turn).
    For fmt!=pdf, only the latest is returned.
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if fmt == "pdf" and all_responses:
        # build a PDF that lists only response_text from each successful turn
        docs = store.get_all_success_by_session(session_id, limit=500)
        if not docs:
            raise HTTPException(status_code=404, detail="No successful runs found for session_id")
        # Collect query/response_text pairs
        lines: list[str] = []
        for d in docs:
            final = d.get("final", {}) if isinstance(d, dict) else {}
            # extract like above
            rt = None
            if isinstance(final, dict):
                rt = final.get("response_text")
                if not (isinstance(rt, str) and rt.strip()):
                    resp = final.get("response")
                    if isinstance(resp, dict):
                        rt = resp.get("response_text")
                        if not (isinstance(rt, str) and rt.strip()):
                            inner = resp.get("response")
                            if isinstance(inner, dict):
                                rt = inner.get("response_text")
            uq = d.get("user_query")
            if isinstance(rt, str) and rt.strip():
                # Compose block with query and response
                q = uq.strip() if isinstance(uq, str) else ""
                block = (f"Q: {q}\nA: {rt.strip()}") if q else (f"A: {rt.strip()}")
                lines.append(block)
        if not lines:
            raise HTTPException(status_code=404, detail="No response_text entries available for this session")
        # Compose a simple joined text with separators
        joined = "\n\n".join(lines)
        # Render via the same PDF builder pathway by forging a minimal run
        fake_run = {"final": {"response_text": joined}}
        p = _build_export_payload(fake_run, "pdf")
        filename = f"trip_{session_id}_all_responses.pdf"
        return Response(content=p["body_bytes"], media_type=p["content_type"], headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        })
    # default: latest single
    doc = store.get_latest_success_by_session(session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No successful runs found for session_id")
    p = _build_export_payload(doc, fmt)
    filename = f"trip_{session_id}_last.{p['ext']}"
    return Response(content=p["body_bytes"], media_type=p["content_type"], headers={
        "Content-Disposition": f"attachment; filename=\"{filename}\""
    })

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
