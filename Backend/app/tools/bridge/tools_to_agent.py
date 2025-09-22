"""
Tools Bridge for TripPlanner Multi-Agent System

This module provides bridge-friendly wrappers for all tools in the app/tools/*
directory, enabling seamless integration between agents and external tools.
It normalizes arguments, handles errors, and provides consistent return formats.

Key features:
- Argument normalization (dict -> Pydantic models)
- Consistent return format with status indicators
- Error handling and validation
- Tool registration and management
- Harmonized key names for consistent agent output merging

The bridge enables agents to easily interact with external tools while maintaining
consistent interfaces and error handling across the entire multi-agent system.

Usage:
    from app.agents.utils.graph_integration import AgentGraphBridge
    from app.tools.bridge.tools_to_agent import register_all_tools

    bridge = AgentGraphBridge(max_workers=12)
    register_all_tools(bridge)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime

# ---------- Imports: discovery tools ----------
# Cities
from app.tools.discovery.city_recommender_tool import (
    city_recommender_tool, CityRecommenderArgs, CountryArg as CityRecCountryArg
)
# FX
from app.tools.pricing.currency_tool import (
    fx_oracle_tool, FxOracleArgs, CountryArg as FxCountryArg
)
# City fares
from app.tools.pricing.city_fare_tool import (
    cityfares_discovery_tool, CityFaresArgs
)
# Intercity fares
from app.tools.pricing.intercity_fare_tool import (
    intercity_discovery_tool, IntercityDiscoveryArgs  # adjust if your names differ
)
# POI
from app.tools.discovery.POI_discovery_tool import (
    poi_discovery_tool, POIDiscoveryArgs  # adjust to your exact names
)
# Restaurants
from app.tools.discovery.restaurants_discovery_tool import (
    restaurants_discovery_tool, RestaurantsDiscoveryArgs
)

# ---------- Imports: post-processing tools ----------
from app.tools.planning.discoveries_costs_tool import (
    discovery_and_cost
)
from app.tools.planning.city_graph_tool import (
    geocost_assembler
)
from app.tools.planning.optimizer_helper_tool import (
    itinerary_optimizer_greedy
)
from app.tools.planning.trip_maker_tool import (
    trip_orchestrator
)
from app.tools.export.writer_report_tool import (
    writer_report
)

# Gap data tool
from app.tools.gap_patch.gap_data_tool import (
    fill_gaps_search_only
)


# ---------- Small normalizers ----------

def _norm_countries(raw: Any, for_fx: bool = False) -> List[Any]:
    """
    Accepts:
      ["Japan","France"]
      [{"country":"Japan"},{"name":"France"}]
      [{"country":"Japan","cities":["Tokyo"]}]
    Returns a list of the respective Pydantic CountryArg for the tool.
    """
    out = []
    if not raw:
        return out
    for c in raw:
        if isinstance(c, str):
            if for_fx:
                out.append(FxCountryArg(country=c))
            else:
                out.append(CityRecCountryArg(country=c))
        elif isinstance(c, dict):
            if for_fx:
                out.append(FxCountryArg(country=c.get("country") or c.get("name")))
            else:
                out.append(CityRecCountryArg(
                    country=c.get("country") or c.get("name"),
                    cities=c.get("cities") or []
                ))
    return out

def _success(result: Dict[str, Any]) -> Dict[str, Any]:
    """Standardized success response"""
    return {"status": "success", "result": result}

def _error(msg: str, partial: Optional[Dict[str, Any]] = None, error_type: str = "tool_error") -> Dict[str, Any]:
    """Standardized error response with consistent structure"""
    out = {
        "status": "error", 
        "error": msg,
        "error_type": error_type,
        "timestamp": datetime.now().isoformat()
    }
    if partial is not None:
        out["partial_result"] = partial
    return out

def _warning(msg: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Standardized warning response for partial success"""
    return {
        "status": "warning",
        "message": msg,
        "result": result,
        "timestamp": datetime.now().isoformat()
    }


# ---------- Wrappers: discovery ----------

def city_recommender_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = CityRecommenderArgs(
            countries=_norm_countries(args.get("countries")),
            dates=args.get("dates"),
            travelers=args.get("travelers") or {"adults": 1, "children": 0},
            musts=args.get("musts", []),
            preferred_cities=args.get("preferred_cities", []),
            preferences=args.get("preferences", {}),
            default_recommend_count=int(args.get("default_recommend_count", 5)),
            max_candidates=int(args.get("max_candidates", 12)),
            model=args.get("model"),
        )
    except Exception as e:
        return _error(f"arg_validation:{e}")

    try:
        res = city_recommender_tool(payload)
        d = res.model_dump()
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def currency_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = FxOracleArgs(
            countries=_norm_countries(args.get("countries"), for_fx=True),
            city_country_map=args.get("city_country_map") or {},
            target_currency=args.get("target_currency"),
            preferences=args.get("preferences") or {},
            musts=args.get("musts") or [],
        )
    except Exception as e:
        return _error(f"arg_validation:{e}")

    try:
        res = fx_oracle_tool(payload)
        d = res.model_dump()
        # Normalize to the shape expected by other tools/agents
        normalized = {
            "provider": d.get("provider"),
            "as_of": d.get("as_of"),
            "base": d.get("base"),
            "target_currency": d.get("target"),
            "rates_base_to_code": d.get("rates") or {},
            "rates_to_target": d.get("to_target") or {},
            "currency_by_country": d.get("currency_by_country") or {},
            "note": d.get("note"),
            "errors": d.get("errors") or [],
        }
        if d.get("errors"):
            return _error("FX conversion errors occurred", normalized, "fx_errors")
        return _success(normalized)
    except Exception as e:
        return _error(f"runtime:{e}")

def city_fare_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = CityFaresArgs(
            cities=args.get("cities", []),
            city_country_map=args.get("city_country_map", {}),
            preferences=args.get("preferences", {}),
            travelers=args.get("travelers"),
            musts=args.get("musts", []),
            fx_target=args.get("fx_target"),
            fx_to_target=args.get("fx_to_target"),
            max_urls_per_city=args.get("max_urls_per_city") or 4,
            model=args.get("model"),
            use_llm=args.get("use_llm"),
        )
    except Exception as e:
        return _error(f"arg_validation:{e}")

    try:
        res = cityfares_discovery_tool(payload)
        d = res.model_dump()
        if d.get("errors"):
            return _error("City fares discovery errors occurred", d, "city_fares_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def intercity_fare_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = IntercityDiscoveryArgs(
            cities=args.get("cities", []),
            city_country_map=args.get("city_country_map", {}),
            preferences=args.get("preferences", {}),
            travelers=args.get("travelers"),
            musts=args.get("musts", []),
            fx_target=args.get("fx_target"),
            fx_to_target=args.get("fx_to_target"),
            # plus any specific knobs your intercity tool expects (e.g., operators_only, modes, etc.)
        )
    except Exception as e:
        return _error(f"arg_validation:{e}")

    try:
        res = intercity_discovery_tool(payload)
        d = res.model_dump()
        if d.get("errors"):
            return _error("Intercity fares discovery errors occurred", d, "intercity_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def poi_discovery_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = POIDiscoveryArgs(
            cities=args.get("cities", []),
            city_country_map=args.get("city_country_map", {}),
            poi_target_per_city=args.get("poi_target_per_city", 15),
            preferences=args.get("preferences", {}),
            travelers=args.get("travelers"),
            musts=args.get("musts", []),
            with_kids=args.get("with_kids"),
            # pass other paging/limits if your tool supports them via args
        )
    except Exception as e:
        return _error(f"arg_validation:{e}")

    try:
        res = poi_discovery_tool(payload)
        d = res.model_dump()
        if d.get("errors"):
            return _error("POI discovery errors occurred", d, "poi_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def restaurants_discovery_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = RestaurantsDiscoveryArgs(
            cities=args.get("cities", []),
            preferences=args.get("preferences", {}),
            travelers=args.get("travelers"),
            musts=args.get("musts", []),
        )
    except Exception as e:
        return _error(f"arg_validation:{e}")

    try:
        res = restaurants_discovery_tool(payload)
        d = res.model_dump()
        if d.get("errors"):
            return _error("Restaurant discovery errors occurred", d, "restaurants_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")


# ---------- Wrappers: post-processing (final phase) ----------

def discoveries_costs_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate POI/restaurants etc. into discovery + rough costs/time."""
    try:
        # Create a minimal AppState from the args
        from app.tools.tools_utils.state import AppState
        payload = AppState(request=args) if args else AppState()
    except Exception as e:
        return _error(f"arg_validation:{e}")
    try:
        res = discovery_and_cost(payload)
        # AppState is returned, convert to dict
        d = res.model_dump() if hasattr(res, 'model_dump') else res
        if d.get("errors"):
            return _error("Discovery costs calculation errors occurred", d, "discoveries_costs_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def city_graph_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build day-level activity graph per city from discovery."""
    try:
        # Create a minimal AppState from the args
        from app.tools.tools_utils.state import AppState
        payload = AppState(request=args) if args else AppState()
    except Exception as e:
        return _error(f"arg_validation:{e}")
    try:
        res = geocost_assembler(payload)
        # AppState is returned, convert to dict
        d = res.model_dump() if hasattr(res, 'model_dump') else res
        if d.get("errors"):
            return _error("City graph creation errors occurred", d, "city_graph_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def optimizer_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Greedy itinerary optimizer."""
    try:
        # Create a minimal AppState from the args
        from app.tools.tools_utils.state import AppState
        payload = AppState(request=args) if args else AppState()
    except Exception as e:
        return _error(f"arg_validation:{e}")
    try:
        res = itinerary_optimizer_greedy(payload)
        # AppState is returned, convert to dict
        d = res.model_dump() if hasattr(res, 'model_dump') else res
        if d.get("errors"):
            return _error("Itinerary optimization errors occurred", d, "optimizer_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def trip_maker_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Produce final day-by-day itinerary cards."""
    try:
        # Create a minimal AppState from the args
        from app.tools.tools_utils.state import AppState
        payload = AppState(request=args) if args else AppState()
    except Exception as e:
        return _error(f"arg_validation:{e}")
    try:
        res = trip_orchestrator(payload)
        # AppState is returned, convert to dict
        d = res.model_dump() if hasattr(res, 'model_dump') else res
        if d.get("errors"):
            return _error("Trip creation errors occurred", d, "trip_maker_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def writer_report_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Human-friendly summary/markdown/HTML export."""
    try:
        # Create a minimal AppState from the args
        from app.tools.tools_utils.state import AppState
        payload = AppState(request=args) if args else AppState()
    except Exception as e:
        return _error(f"arg_validation:{e}")
    try:
        res = writer_report(payload)
        # AppState is returned, convert to dict
        d = res.model_dump() if hasattr(res, 'model_dump') else res
        if d.get("errors"):
            return _error("Report generation errors occurred", d, "writer_report_errors")
        return _success(d)
    except Exception as e:
        return _error(f"runtime:{e}")

def gap_data_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fill missing data gaps using web search and LLM extraction."""
    try:
        result, patches = fill_gaps_search_only(args)
        return {"status": "success", "result": result, "patched": patches}
    except Exception as e:
        return _error(f"Gap data filling failed: {e}", error_type="gap_data_errors")


# ---------- Registration helper ----------

def register_all_tools(bridge) -> None:
    """
    Register all wrappers with the AgentGraphBridge.
    Names mirror your interpreter/planner vocabulary:
      - discovery:   "city_recommender", "currency", "city_fare", "intercity_fare", "poi_discovery", "restaurants_discovery"
      - final phase: "discoveries_costs", "city_graph", "optimizer", "trip_maker", "writer_report"
    """
    # Discovery
    bridge.register_tool("city_recommender", city_recommender_wrapper)
    bridge.register_tool("currency",         currency_wrapper)
    bridge.register_tool("city_fare",        city_fare_wrapper)
    bridge.register_tool("intercity_fare",   intercity_fare_wrapper)
    bridge.register_tool("poi_discovery",    poi_discovery_wrapper)
    bridge.register_tool("restaurants_discovery", restaurants_discovery_wrapper)

    # Final phase
    bridge.register_tool("discoveries_costs", discoveries_costs_wrapper)
    bridge.register_tool("city_graph",        city_graph_wrapper)
    bridge.register_tool("optimizer",         optimizer_wrapper)
    bridge.register_tool("trip_maker",        trip_maker_wrapper)
    bridge.register_tool("writer_report",     writer_report_wrapper)
    
    # Gap filling
    bridge.register_tool("gap_data",          gap_data_wrapper)
