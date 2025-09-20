# app/agents/data_fetcher_agent.py
from __future__ import annotations
from typing import Any, Dict, Callable, List, Optional
from dataclasses import dataclass, field
import importlib
import sys
from pathlib import Path
import traceback

# Ensure project root (the parent of "app") is on sys.path
# so "app.graph.nodes.*" absolute imports work whether you run as a module or a script.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Try your AppState; fall back to a tiny stub so tests can run.
try:
    from app.graph.state import AppState
except Exception:
    @dataclass
    class AppState:
        request: Dict[str, Any]
        logs: List[str] = field(default_factory=list)
        meta: Dict[str, Any] = field(default_factory=dict)

ToolFn = Callable[[AppState], AppState]

# ---- Tool registry (match your filesystem exactly; case-sensitive) ----
_TOOL_REGISTRY: Dict[str, str] = {
    # discovery / fetch tools
    "cities.recommender":    "app.graph.nodes.city_recommender:city_recommender",
    "fx.oracle":             "app.graph.nodes.currency:fx_oracle",
    "fares.city":            "app.graph.nodes.city_fare:cityfares_discovery",
    "fares.intercity":       "app.graph.nodes.intercity_fare:intercity_discovery",
    "poi.discovery":         "app.graph.nodes.POI_discovery:poi_discovery",
    "restaurants.discovery": "app.graph.nodes.restaurants_discovery:restaurants_discovery",

    # post-processing / compose
    # "discovery.costs":       "app.graph.nodes.discoveries_costs:discoveries_costs",
    # "graph.city":            "app.graph.nodes.city_graph:geocost_assembler",
    # "opt.greedy":            "app.graph.nodes.optimizer_helper:itinerary_optimizer_greedy",
    # "trip.maker":            "app.graph.nodes.trip_maker:trip_orchestrator",
    # "writer.report":         "app.graph.nodes.writer_report:writer_report",
}

def _import_tool(qualname: str, logs: Optional[List[str]] = None) -> Optional[ToolFn]:
    """
    Import "package.module:attr" with detailed error logging.
    """
    try:
        mod_path, attr = qualname.split(":")
    except ValueError:
        if logs is not None:
            logs.append(f"[Import] malformed tool path: {qualname!r}")
        return None

    try:
        mod = importlib.import_module(mod_path)
    except Exception as e:
        if logs is not None:
            tb = traceback.format_exc(limit=2)
            logs.append(f"[Import] failed to import module {mod_path!r}: {e!r}\n{tb}")
        return None

    try:
        fn = getattr(mod, attr)
        return fn  # type: ignore[return-value]
    except AttributeError as e:
        if logs is not None:
            logs.append(f"[Import] module {mod_path!r} has no attr {attr!r}")
        return None
    except Exception as e:
        if logs is not None:
            tb = traceback.format_exc(limit=2)
            logs.append(f"[Import] error getting {attr!r} from {mod_path!r}: {e!r}\n{tb}")
        return None

def _resolve_tool(tool_id: str, logs: Optional[List[str]] = None) -> Optional[ToolFn]:
    qual = _TOOL_REGISTRY.get(tool_id)
    if not qual:
        if logs is not None:
            logs.append(f"[DataFetcher] not registered: {tool_id}")
        return None
    return _import_tool(qual, logs)

def run_data_fetcher(plan: Dict[str, Any], request: Dict[str, Any]) -> AppState:
    """
    Executes tools in plan['tool_plan'] over the request dict, in order.
    Skips tools that aren't available yet (but logs the *reason* precisely).
    """
    tool_plan = plan.get("tool_plan") or []
    print("this is the tool plan", tool_plan)
    state = AppState(request=request, logs=[], meta={})

    # sanity: make sure app & graph are packages
    for pkg in ["app", "app.graph", "app.graph.nodes", "app.graph.nodes_new"]:
        try:
            importlib.import_module(pkg)
        except Exception as e:
            state.logs.append(f"[DataFetcher] WARN: package import failed for {pkg}: {e!r}")

    for tool_id in tool_plan:
        print("this is the tool id", tool_id)
        fn = _resolve_tool(tool_id, state.logs)
        if not fn:
            state.logs.append(f"[DataFetcher] SKIP: {tool_id} (tool not registered or import failed)")
            continue

        if state.meta.get("requires_input"):
            state.logs.append(f"[DataFetcher] HALT: upstream requires_input={state.meta['requires_input']}")
            break

        try:
            state.logs.append(f"[DataFetcher] RUN: {tool_id}")
            state = fn(state)  # all current tools are AppState -> AppState
        except Exception as e:
            tb = traceback.format_exc(limit=4)
            state.logs.append(f"[DataFetcher] ERROR: {tool_id}: {e!r}\n{tb}")
            # continue so the critic can try to fill gaps
            continue
        break

    return state

if __name__ == "__main__":
    # tiny manual smoke run
    plan = {"tool_plan": ["fares.intercity"]}  # change as you like
    req = {"cities": ["Rome", "Florence"], "target_currency": "EUR"}
    st = run_data_fetcher(plan, req)
    print("-- LOGS --")
    for line in st.logs:
        print(line)
    print("-- META --")
    print(st.meta)
    print("-- REQUEST --")
    print(st.request)
