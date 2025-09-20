# app/graph/nodes_new/final_tools.py
from __future__ import annotations

from typing import Any, Dict, List
from dataclasses import dataclass, field
from langgraph.graph import END

# Import tool functions with resilient fallbacks to module paths
def _import_or_none(path: str, name: str):
    try:
        mod = __import__(path, fromlist=[name])
        return getattr(mod, name, None)
    except Exception:
        return None

# Try common locations (project vs flat)
_discovery_fn = (
    _import_or_none("app.graph.nodes.discoveries_costs_tool", "discovery_and_cost")
    or _import_or_none("app.graph.nodes.discoveries_costs_tool", "discovery_and_cost")
    or _import_or_none("discoveries_costs_tool", "discovery_and_cost")
)
_citygraph_fn = (
    _import_or_none("app.tools.city_graph_tool", "geocost_assembler")
    or _import_or_none("app.graph.nodes.city_graph_tool", "geocost_assembler")
    or _import_or_none("city_graph_tool", "geocost_assembler")
)
_opt_fn = (
    _import_or_none("app.tools.optimizer_helper_tool", "itinerary_optimizer_greedy")
    or _import_or_none("app.graph.nodes.optimizer_helper_tool", "itinerary_optimizer_greedy")
    or _import_or_none("optimizer_helper_tool", "itinerary_optimizer_greedy")
)
_trip_fn = (
    _import_or_none("app.tools.trip_maker_tool", "trip_orchestrator")
    or _import_or_none("app.graph.nodes.trip_maker_tool", "trip_orchestrator")
    or _import_or_none("trip_maker_tool", "trip_orchestrator")
)

@dataclass
class AppState:
    request: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

# ------------- shared helpers -------------
def build_appstate_from_travel_state(state: Dict[str, Any]) -> AppState:
    # Defer to trip_interpreter adapter if available
    try:
        from app.graph.nodes_new.trip_interpreter import build_appstate_from_travel_state as _build
        return _build(state)
    except Exception:
        return AppState(request={"cities": state.get("cities") or []}, logs=[], meta={})

def _merge_back(state: Dict[str, Any], app: AppState) -> None:
    req = app.request or {}
    if "itinerary" in req:
        state["itinerary"] = req.get("itinerary")
    if "discovery" in req:
        state["final_discovery"] = req.get("discovery")
    if "geocost" in req:
        state["final_geocost"] = req.get("geocost")
    if app.logs:
        state.setdefault("logs", []).extend([f"[final] {line}" for line in app.logs])

# ------------- Node functions -------------
def node_trip_interpret(state: Dict[str, Any]) -> Dict[str, Any]:
    from app.graph.nodes_new.trip_interpreter import interpret_trip_plan
    user_msg = state.get("user_message") or ""
    if not state.get("trip_plan_queue"):
        plan = interpret_trip_plan(user_msg, state)
        state["trip_plan_queue"] = list(plan.get("tool_plan") or [])
        state["logs"] = (state.get("logs") or []) + [f"[trip.interpret] plan={state['trip_plan_queue']} | notes={plan.get('notes','')}"]
    if "trip_appstate" not in state or not state["trip_appstate"]:
        state["trip_appstate"] = build_appstate_from_travel_state(state)
        state["logs"].append("[trip.interpret] AppState initialized")
    return state

def node_trip_route_passthrough(state: Dict[str, Any]) -> Dict[str, Any]:
    return state

def trip_router(state: Dict[str, Any]) -> str:
    q = state.get("trip_plan_queue") or []
    if not q:
        state.setdefault("logs", []).append("[trip.router] done → END")
        return END
    nxt = q[0]
    state.setdefault("logs", []).append(f"[trip.router] → {nxt}")
    return nxt

def _pop_done(state: Dict[str, Any], name: str) -> None:
    q = state.get("trip_plan_queue") or []
    if q and q[0] == name:
        state["trip_plan_queue"] = q[1:]
    state.setdefault("trip_done_tools", []).append(name)

def node_discovery_costs(state: Dict[str, Any]) -> Dict[str, Any]:
    app: AppState = state.get("trip_appstate")
    if app is None:
        app = build_appstate_from_travel_state(state)
    if _discovery_fn is None:
        state.setdefault("logs", []).append("[discovery.costs] MISSING FUNCTION import")
        _pop_done(state, "discovery.costs")
        return state
    app = _discovery_fn(app)  # type: ignore
    state["trip_appstate"] = app
    _merge_back(state, app)
    _pop_done(state, "discovery.costs")
    return state

def node_city_graph(state: Dict[str, Any]) -> Dict[str, Any]:
    app: AppState = state.get("trip_appstate")
    if app is None:
        app = build_appstate_from_travel_state(state)
    if _citygraph_fn is None:
        state.setdefault("logs", []).append("[city.graph] MISSING FUNCTION import")
        _pop_done(state, "city.graph")
        return state
    app = _citygraph_fn(app)  # type: ignore
    state["trip_appstate"] = app
    _merge_back(state, app)
    _pop_done(state, "city.graph")
    return state

def node_opt_greedy(state: Dict[str, Any]) -> Dict[str, Any]:
    app: AppState = state.get("trip_appstate")
    if app is None:
        app = build_appstate_from_travel_state(state)
    if _opt_fn is None:
        state.setdefault("logs", []).append("[opt.greedy] MISSING FUNCTION import")
        _pop_done(state, "opt.greedy")
        return state
    app = _opt_fn(app)  # type: ignore
    state["trip_appstate"] = app
    _merge_back(state, app)
    _pop_done(state, "opt.greedy")
    return state

def node_trip_maker(state: Dict[str, Any]) -> Dict[str, Any]:
    app: AppState = state.get("trip_appstate")
    if app is None:
        app = build_appstate_from_travel_state(state)
    if _trip_fn is None:
        state.setdefault("logs", []).append("[trip.maker] MISSING FUNCTION import")
        _pop_done(state, "trip.maker")
        return state
    app = _trip_fn(app)  # type: ignore
    state["trip_appstate"] = app
    _merge_back(state, app)
    _pop_done(state, "trip.maker")
    return state
