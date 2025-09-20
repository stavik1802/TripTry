# app/graph/nodes_new/trip_interpreter.py
from __future__ import annotations

import os, json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ------------------ Small shared types ------------------
@dataclass
class AppState:
    request: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


ALLOWED_FINAL_TOOLS = ["discovery.costs", "city.graph", "opt.greedy", "trip.maker"]

# ------------------ LLM prompt ------------------
_SYS = (
    "You are a planning interpreter for a travel pipeline's FINAL PHASE.\n"
    "Given the user's ask and the artifacts already collected (cities, POIs, restaurants, fares, intercity),\n"
    "choose which FINAL tools to run and in which order. Always return strict JSON.\n"
    "Available tools:\n"
    "- discovery.costs: Aggregate discovered POIs/restaurants and produce a 'discovery' + rough costs/time estimates per city.\n"
    "- city.graph: Build a day-level activity graph per city from discovery (nodes = hotel, POIs, meals; edges = travel-time).\n"
    "- opt.greedy: Greedy itinerary optimizer that assigns days and balances time/costs.\n"
    "- trip.maker: Produce the final day-by-day itinerary cards from the optimized structure.\n"
    "Typical order for full planning: ['discovery.costs','city.graph','opt.greedy','trip.maker'].\n"
    "If the user only wants costs, Or a non planning intent, you can stop after 'discovery.costs'. If they only asked for a high-level plan, you can do ['city.graph','trip.maker'] provided 'discovery' exists.\n"
    "Rules:\n"
    "1) Only use tools from the allowed list exactly as spelled.\n"
    "2) Ensure dependencies: 'city.graph' requires 'discovery.costs' first if 'discovery' is missing.\n"
    "3) 'opt.greedy' requires the city graph, and 'trip.maker' requires either the graph or the optimizer output.\n"
    "Return JSON: {\"tool_plan\": [..], \"notes\": \"...\"}\n"
)

def _oa_client() -> Optional[OpenAI]:
    if OpenAI is None:
        return None
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return None
    return OpenAI(api_key=key)

def interpret_trip_plan(user_message: str, state_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Return {'tool_plan':[...], 'notes': str}. Fallback to default chain on errors."""
    plan_default = ["discovery.costs", "city.graph", "opt.greedy", "trip.maker"]
    intent = ((state_snapshot.get("interp") or {}).get("intent") or "").strip()
    if intent in ("city_fares", "intercity_fares"):
        return {"tool_plan": [], "notes": "No final tools needed for pure fares intent."}

    oa = _oa_client()
    if oa is None:
        return {"tool_plan": plan_default, "notes": "No LLM available; using default end-to-end plan."}

    try:
        content = {
            "user_message": (user_message or "")[:600],
            "artifacts": {
                "cities": state_snapshot.get("cities"),
                "poi": list((state_snapshot.get("poi") or {}).keys()) if isinstance(state_snapshot.get("poi"), dict) else bool(state_snapshot.get("poi")),
                "restaurants": list((state_snapshot.get("restaurants") or {}).keys()) if isinstance(state_snapshot.get("restaurants"), dict) else bool(state_snapshot.get("restaurants")),
                "city_fares": bool((state_snapshot.get("city_fares") or {}).get("city_fares")),
                "intercity": bool((state_snapshot.get("intercity") or {}).get("hops")),
                "fx_meta": bool(state_snapshot.get("fx_meta")),
            },
            "preferences": (state_snapshot.get("interp") or {}).get("preferences") or {},
        }
        resp = oa.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYS},
                {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        plan = [t for t in (data.get("tool_plan") or []) if t in ALLOWED_FINAL_TOOLS]
        if not plan:
            plan = plan_default
        notes = (data.get("notes") or "").strip()
        return {"tool_plan": plan, "notes": notes}
    except Exception as e:
        return {"tool_plan": plan_default, "notes": f"fallback (error: {e})"}

# ------------------ AppState adapter ------------------
def build_appstate_from_travel_state(state: Dict[str, Any]) -> AppState:
    """Create an AppState.request the final-phase tools understand."""
    req: Dict[str, Any] = {}
    # Cities & simple discovery blob
    cities = state.get("cities") or []
    poi_blob = (state.get("poi") or {}).get("poi_by_city") or {}
    rest_blob = (state.get("restaurants") or {}).get("names_by_city") or {}
    discovery_cities: Dict[str, Any] = {}
    for c in cities:
        city_pois = []
        if c in poi_blob:
            for p in (poi_blob.get(c) or {}).get("pois") or []:
                nm = (p.get("name") or "").strip()
                if nm:
                    city_pois.append({"name": nm})
        rest_names = []
        # rest_blob[c] is a dict of buckets -> list of {name}
        rest_bucket = rest_blob.get(c) or {}
        for arr in rest_bucket.values():
            for r in (arr or []):
                nm = (r.get("name") or "").strip()
                if nm:
                    rest_names.append({"name": nm})
        if city_pois or rest_names:
            discovery_cities[c] = {"pois": city_pois, "restaurants": rest_names}

    if discovery_cities:
        req["discovery"] = {"cities": discovery_cities}

    # Meta context
    req["cities"] = list(cities)
    req["city_country_map"] = state.get("city_country_map") or {}
    req["fx_meta"] = state.get("fx_meta") or {}
    req["intercity"] = state.get("intercity") or {}

    # Preferences & travelers for downstream context
    interp = state.get("interp") or {}
    req["preferences"] = interp.get("preferences") or {}
    req["travelers"] = interp.get("travelers") or {"adults": 2, "children": 0}
    req["target_currency"] = (interp.get("target_currency") or (state.get("fx_meta") or {}).get("target") or "USD")

    return AppState(request=req, logs=[], meta={})
