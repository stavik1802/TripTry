# app/graph/nodes/gap_search_fill_node.py
from __future__ import annotations
from typing import Any, Dict, List
from app.graph.gap.specs import build_missing_items
from app.graph.gap.patch import exists_selector
from app.graph.nodes.gap_data_tool import fill_gaps_search_only

def _collect_missing_now(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = build_missing_items(state)
    # keep only those whose path doesn't exist yet
    out: List[Dict[str, Any]] = []
    for it in items:
        if not exists_selector(state, it["path"]):
            out.append(it)
    return out

def node_gap_search_fill(state: Dict[str, Any]) -> Dict[str, Any]:
    missing = _collect_missing_now(state)
    if not missing:
        state.setdefault("logs", []).append("[gap] nothing to fill")
        state["gap_filled_count"] = 0
        state["gap_done"] = True
        return state

    args = {
        "message": state.get("user_message") or "",
        "request_snapshot": state,
        "missing": missing,
        "max_queries_per_item": 4,
        "max_results_per_query": 6,
    }
    try:
        result, patched = fill_gaps_search_only(args)
        state.clear()
        state.update(patched)
        state.setdefault("logs", []).extend(result.get("logs") or [])
        state["gap_filled_count"] = len(result.get("items") or [])
        state["gap_done"] = False
        state.setdefault("done_tools", []).append("gap.search_only")
    except Exception as e:
        state.setdefault("logs", []).append(f"[gap] ERROR {e!r}")
        state["gap_filled_count"] = 0
        state["gap_done"] = False
    return state

def cond_gap_more_or_done(state: Dict[str, Any]) -> str:
    still_missing = _collect_missing_now(state)
    return "more" if still_missing else "done"
