"""
Gap Detection Specifications for TripPlanner Multi-Agent System

This module defines specifications and detection functions for identifying missing
data gaps in trip planning research. It provides utilities to detect missing
POIs, restaurants, fares, and other travel-related data.

Key features:
- Gap detection functions for various data types
- JSON schema definitions for data validation
- Tool completion tracking and validation
- Data structure navigation and querying utilities
- Missing data identification algorithms

The module enables systematic identification of data gaps, allowing the gap agent
to efficiently fill missing information and ensure comprehensive trip planning data.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

# ---------- Minimal JSON Schemas (aligned to your Pydantic) ----------
SCHEMA_MONEY       = '{"type":"object","properties":{"amount":{"type":"number"},"currency":{"type":"string"}}}'
SCHEMA_NUM         = '{"type":"number"}'
SCHEMA_STR         = '{"type":"string"}'
SCHEMA_POI_PRICE   = '{"type":"object","properties":{"adult":{"type":"number"},"child":{"type":"number"},"currency":{"type":"string"}}}'
SCHEMA_COORDS      = '{"type":"object","properties":{"lat":{"type":"number"},"lon":{"type":"number"}}}'

# If you ever change envelopes, keep these constants in sync
CITY_FARES_BASE = "city_fares.city_fares"   # state["city_fares"]["city_fares"][<city>]
INTERCITY_BASE  = "intercity.hops"          # state["intercity"]["hops"]["A -> B"]


# ----------------------- tiny helpers -----------------------
def _tool_done(state: Dict[str, Any], tool: str) -> bool:
    return tool in set(state.get("done_tools") or [])

def _get(root: Dict[str, Any], dotted: str) -> Any:
    cur: Any = root
    for tok in dotted.split("."):
        if not isinstance(cur, dict) or tok not in cur:
            return None
        cur = cur[tok]
    return cur

def _exists(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, (str, list, dict)) and not v:
        return False
    return True

def _money_ok(v: Any) -> bool:
    if not isinstance(v, dict):
        return False
    amt = v.get("amount")
    ccy = v.get("currency")
    return (amt is not None) and bool(str(ccy or "").strip())

def _add(items: List[Dict[str, Any]], path: str, desc: str, schema: Optional[str],
         hints: List[str], ctx: Dict[str, Any]) -> None:
    items.append({
        "path": path,
        "description": desc,
        "schema": schema,
        "hints": hints,
        "context": ctx,
        "allow_source_patch": True,
    })


# ----------------------- CITY FARES -----------------------
def _missing_city_fares(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not _tool_done(state, "fares.city"):
        return out

    cf_root = _get(state, CITY_FARES_BASE)
    if not isinstance(cf_root, dict):
        return out

    city_country = state.get("city_country_map") or {}

    for city, payload in cf_root.items():
        if not isinstance(payload, dict):
            continue
        ctx = {"city": city, "country": city_country.get(city)}

        # Transit (MoneyOut)
        for key, label in (
            ("single",      "single-ride transit price (adult) with currency"),
            ("day_pass",    "day pass transit price (adult) with currency"),
            ("weekly_pass", "weekly pass transit price (adult) with currency"),
        ):
            p = f"{CITY_FARES_BASE}.{city}.transit.{key}"
            if not _money_ok(_get(state, p)):
                _add(out, p, label, SCHEMA_MONEY, ["fare", "official", "price"], ctx)

        # Taxi (floats + currency)
        for key, label, schema in (
            ("base",    "official taxi base fare", SCHEMA_NUM),
            ("per_km",  "taxi per-km fare",        SCHEMA_NUM),
            ("per_min", "taxi per-minute fare",    SCHEMA_NUM),
        ):
            p = f"{CITY_FARES_BASE}.{city}.taxi.{key}"
            if not _exists(_get(state, p)):
                _add(out, p, label, schema, ["taxi tariff", "official"], ctx)

        p_cur = f"{CITY_FARES_BASE}.{city}.taxi.currency"
        v_cur = _get(state, p_cur)
        if not (isinstance(v_cur, str) and len(v_cur.strip()) >= 3):
            _add(out, p_cur, "taxi currency ISO code", SCHEMA_STR, ["currency", "ISO"], ctx)

    return out


# ----------------------- INTERCITY -----------------------
def _split_hop(key: str) -> (str, str):
    if "->" in key:
        a, b = key.split("->", 1)
        return a.strip(), b.strip()
    return key, ""

def _missing_intercity(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not _tool_done(state, "fares.intercity"):
        return out

    hops = _get(state, INTERCITY_BASE)
    if not isinstance(hops, dict):
        # if your tool still returns a list, skip to avoid list patching
        return out

    for hop_key, hop_payload in hops.items():
        if not isinstance(hop_payload, dict):
            continue
        frm, to = _split_hop(hop_key)
        base_ctx = {"from": frm, "to": to}

        for mode in ("rail", "bus", "flight"):
            mode_obj = hop_payload.get(mode, {})
            if not isinstance(mode_obj, dict):
                continue
            ctx = {**base_ctx, "mode": mode}

            p_dur = f"{INTERCITY_BASE}.{hop_key}.{mode}.duration_min"
            if not _exists(_get(state, p_dur)):
                _add(out, p_dur, "typical travel duration (minutes)", SCHEMA_NUM,
                     ["timetable", "duration", "schedule"], ctx)

            p_price = f"{INTERCITY_BASE}.{hop_key}.{mode}.price"
            if not _money_ok(_get(state, p_price)):
                _add(out, p_price, "one-way price with currency", SCHEMA_MONEY,
                     ["price", "fare", "official"], ctx)

    return out


# ----------------------- POIs -----------------------
def _missing_pois(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Only checks POIs that already exist in state["poi"]["poi_by_city"][city]["pois"].
    Uses selector form: poi.poi_by_city.<city>.pois[name=<name>].field
    """
    out: List[Dict[str, Any]] = []
    if not _tool_done(state, "poi.discovery"):
        return out

    by_city = ((state.get("poi") or {}).get("poi_by_city") or {})
    if not isinstance(by_city, dict):
        return out

    city_country = state.get("city_country_map") or {}

    for city, payload in by_city.items():
        pois = (payload or {}).get("pois") or []
        if not isinstance(pois, list):
            continue
        for poi in pois:
            if not isinstance(poi, dict):
                continue
            name = (poi.get("name") or "").strip()
            if not name:
                continue
            ctx = {"city": city, "country": city_country.get(city), "name": name}
            base = f"poi.poi_by_city.{city}.pois[name={name}]"

            # official_url (str)
            if not _exists(poi.get("official_url")):
                _add(out, f"{base}.official_url", "official website URL", None,
                     ["official site", "homepage"], ctx)

            # hours (object, no strict schema)
            if not _exists(poi.get("hours")):
                _add(out, f"{base}.hours", "opening hours by day", None,
                     ["hours", "opening times", "schedule"], ctx)

            # price (PriceOut)
            v_price = poi.get("price")
            if not (isinstance(v_price, dict) and (v_price.get("adult") is not None or v_price.get("child") is not None) and v_price.get("currency")):
                _add(out, f"{base}.price", "admission price (adult/child) + currency",
                     SCHEMA_POI_PRICE, ["admission", "ticket price", "official"], ctx)

            # coords (lat/lon)
            v_coords = poi.get("coords")
            if not (isinstance(v_coords, dict) and (v_coords.get("lat") is not None) and (v_coords.get("lon") is not None)):
                _add(out, f"{base}.coords", "latitude/longitude", SCHEMA_COORDS,
                     ["coordinates", "latitude", "longitude"], ctx)

    return out


# ----------------------- RESTAURANTS -----------------------
def _missing_restaurants(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Only fill URLs for known restaurant names already present in names_by_city.
    We address list entries via selector: restaurants.names_by_city.<city>.<group>[name=<name>].url
    """
    out: List[Dict[str, Any]] = []
    if not _tool_done(state, "restaurants.discovery"):
        return out

    names_by_city = ((state.get("restaurants") or {}).get("names_by_city") or {})
    if not isinstance(names_by_city, dict):
        return out

    city_country = state.get("city_country_map") or {}

    for city, groups in names_by_city.items():
        if not isinstance(groups, dict):
            continue
        for group_key, arr in (groups or {}).items():
            if not isinstance(arr, list):
                continue
            for rec in arr:
                if not isinstance(rec, dict):
                    continue
                name = (rec.get("name") or "").strip()
                if not name:
                    continue
                if _exists(rec.get("url")):
                    continue  # already has URL
                ctx = {"city": city, "country": city_country.get(city), "name": name}
                p = f"restaurants.names_by_city.{city}.{group_key}[name={name}].url"
                _add(out, p, "restaurant official/primary URL", None,
                     ["official site", "homepage", "menu"], ctx)

    return out


# ----------------------- Entry Point -----------------------
def build_missing_items(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Emit specs ONLY for fields that belong to artifacts already produced by the tools.
    No enrichment beyond each tool's schema contract.
    """
    items: List[Dict[str, Any]] = []
    items += _missing_city_fares(state)
    items += _missing_intercity(state)
    items += _missing_pois(state)
    items += _missing_restaurants(state)
    return items
