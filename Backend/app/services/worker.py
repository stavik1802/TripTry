# app/services/worker.py
from __future__ import annotations
import os, sys, traceback
from datetime import datetime, timezone

from app.graph.state import AppState
from app.graph.build import build_graph
from app.services.store import get_run, update_run  # you already have create_run/get_run
# from app.services.db import update_run            # if using another module

GRAPH = build_graph()  # compile once per process

def _now(): return datetime.now(timezone.utc)

def run_once(run_id: str) -> None:
    doc = get_run(run_id)
    if not doc:
        return
    # mark running
    update_run(run_id, {"status": "running", "updated_at": _now()})

    try:
        state = AppState(request=doc["request"], logs=[], meta={})
        out_state = GRAPH.invoke(state)

        # collect outputs you care about
        req = out_state.request
        result = {
            "report": req.get("report"),
            "trip": req.get("trip"),
            "discovery": req.get("discovery"),
            "geocost": req.get("geocost"),
            "intercity": req.get("intercity"),
            "logs_tail": (out_state.logs or [])[-10:],
        }
        update_run(run_id, {
            "status": "done",
            "result": result,
            "updated_at": _now(),
        })
    except Exception as e:
        update_run(run_id, {
            "status": "error",
            "errors": [{"ts": _now().isoformat(), "msg": str(e), "trace": traceback.format_exc()}],
            "updated_at": _now(),
        })

if __name__ == "__main__":
    rid = sys.argv[1] if len(sys.argv) > 1 else None
    if rid: run_once(rid)
