from __future__ import annotations
import math
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
import re

from app.graph.state import AppState  # or stub in tests if unavailable


# --------------------------- helpers ---------------------------

def _as_list(x) -> List[Any]:
    return x if isinstance(x, list) else []

def _days_between_iso(start: Optional[str], end: Optional[str]) -> int:
    """Inclusive nights approximation: max(1, (end - start).days)."""
    if not start or not end:
        return 1
    try:
        d0 = date.fromisoformat(start[:10])
        d1 = date.fromisoformat(end[:10])
        n = (d1 - d0).days
        return max(1, n)
    except Exception:
        return 1

def _dedupe(items: List[Dict[str, Any]], key=lambda d: (d.get("name","").strip().lower(), (d.get("url") or "").strip().lower())):
    seen = set(); out = []
    for it in items:
        k = key(it)
        if k in seen:
            continue
        seen.add(k); out.append(it)
    return out

def _money(amount: Optional[float], currency: Optional[str]) -> Optional[Dict[str, Any]]:
    if amount is None or currency is None:
        return None
    return {"amount": float(amount), "currency": currency}

def _first_currency(*cands: Optional[str]) -> Optional[str]:
    for c in cands:
        if isinstance(c, str) and len(c) >= 3:
            return c.upper()
    return None

def _ceil_div(a: float, b: float) -> int:
    return int(math.ceil(a / b)) if a is not None and b else 0

# add this helper near the other helpers
def _coerce_dates(dates_field) -> tuple[Optional[str], Optional[str]]:
    """Accept dict or string; return (start, end) ISO-like or (None, None)."""
    if isinstance(dates_field, dict):
        start = (dates_field.get("start") or None)
        end   = (dates_field.get("end") or None)
        return (start[:10] if isinstance(start, str) else None,
                end[:10]   if isinstance(end, str)   else None)
    if isinstance(dates_field, str):
        # grab first two YYYY-MM-DD tokens if present
        toks = re.findall(r"\d{4}-\d{2}-\d{2}", dates_field)
        start = toks[0] if len(toks) >= 1 else None
        end   = toks[1] if len(toks) >= 2 else None
        return (start, end)
    return (None, None)



# --------------------------- collectors (Discovery_Join) ---------------------------

def _collect_pois(req: Dict[str, Any], city: str) -> List[Dict[str, Any]]:
    """
    Accepts either:
      - req["poi_results"][city] = [{name, price?, hours?, sources?}, ...]
      - OR req["pois_by_city"][city] = ["POI1", ...] (strings or dicts with 'name')
    Normalizes to: [{name, price|null, hours|null, sources:[]}]
    """
    pois_out: List[Dict[str, Any]] = []
    poi_results = (req.get("poi_results") or {}).get(city)
    if isinstance(poi_results, list) and poi_results and isinstance(poi_results[0], dict):
        for p in poi_results:
            name = (p.get("name") or "").strip()
            if not name: continue
            pois_out.append({
                "name": name,
                "price": p.get("price"),        # expected Money or None
                "hours": p.get("hours"),        # keep as-is if present
                "sources": _as_list(p.get("sources"))[:6],
            })
    else:
        for x in _as_list((req.get("pois_by_city") or {}).get(city)):
            if isinstance(x, str):
                nm = x.strip()
            elif isinstance(x, dict) and x.get("name"):
                nm = str(x["name"]).strip()
            else:
                continue
            if nm:
                pois_out.append({"name": nm, "price": None, "hours": None, "sources": []})
    return pois_out

def _collect_city_fares(req: Dict[str, Any], city: str) -> Dict[str, Any]:
    fares = (req.get("city_fares") or {}).get(city) or {}
    tr = fares.get("transit") or {}
    tx = fares.get("taxi") or {}
    return {
        "transit": {
            "single": tr.get("single"),          # Money or None
            "day_pass": tr.get("day_pass"),      # Money or None
            "weekly_pass": tr.get("weekly_pass"),# Money or None
            "sources": _as_list(tr.get("sources"))[:8],
        },
        "taxi": {
            "base": tx.get("base"),
            "per_km": tx.get("per_km"),
            "per_min": tx.get("per_min"),
            "currency": tx.get("currency"),
            "sources": _as_list(tx.get("sources"))[:8],
        },
    }

def _collect_restaurants(req: Dict[str, Any], city: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (links_list, names_list)
    links_list items: {name,url,near_poi}
    names_list items: {name,url|null,source,near_poi}
    """
    links_raw = (req.get("restaurants") or {}).get(city) or {}
    names_raw = (req.get("restaurant_names") or {}).get(city) or {}

    links: List[Dict[str, Any]] = []
    for poi, arr in links_raw.items():
        for it in _as_list(arr):
            nm = (it.get("name") or "").strip()
            url = (it.get("url") or "").strip()
            if nm and url:
                links.append({"name": nm, "url": url, "near_poi": poi})

    names: List[Dict[str, Any]] = []
    for poi, arr in names_raw.items():
        for it in _as_list(arr):
            nm = (it.get("name") or "").strip()
            src = (it.get("source") or "").strip()
            url = it.get("url") or None
            if nm and src:
                names.append({"name": nm, "url": (url or None), "source": src, "near_poi": poi})

    links = _dedupe(links)
    names = _dedupe(names, key=lambda d: d.get("name","").strip().lower())
    return links[:200], names[:300]


# --------------------------- Cost_Inference ---------------------------

def _infer_transit_costs(city_fares: Dict[str, Any], rides_per_day: int, stay_days: int) -> Dict[str, Any]:
    tr = (city_fares or {}).get("transit") or {}
    single = (tr.get("single") or {})
    dayp   = (tr.get("day_pass") or {})
    weekp  = (tr.get("weekly_pass") or {})

    single_amt, single_ccy = single.get("amount"), single.get("currency")
    day_amt, day_ccy       = dayp.get("amount"), dayp.get("currency")
    week_amt, week_ccy     = weekp.get("amount"), weekp.get("currency")

    ccy = _first_currency(day_ccy, single_ccy, week_ccy)

    # break-even rides for day-pass
    break_even = None
    if single_amt and day_amt:
        try:
            break_even = int(math.ceil(day_amt / single_amt))
        except Exception:
            break_even = None

    # per-day choice (single vs day)
    per_day_cost = None
    per_day_choice = None
    if single_amt is not None and day_amt is not None:
        singles_cost = rides_per_day * single_amt
        per_day_cost = min(singles_cost, day_amt)
        per_day_choice = "day_pass" if day_amt <= singles_cost else "single"
    elif single_amt is not None:
        per_day_cost = rides_per_day * single_amt
        per_day_choice = "single"
    elif day_amt is not None:
        per_day_cost = day_amt
        per_day_choice = "day_pass"

    # weekly option: if staying >=5 days and weekly available, compute per-day avg
    weekly_used = False
    weekly_per_day = None
    if week_amt and stay_days >= 5:
        weekly_per_day = week_amt / float(stay_days or 1)
        if per_day_cost is None or weekly_per_day < per_day_cost:
            per_day_cost = weekly_per_day
            per_day_choice = "weekly_pass"
            weekly_used = True

    return {
        "rides_per_day": rides_per_day,
        "break_even_rides_for_day_pass": break_even,
        "per_day_choice": per_day_choice,
        "per_day_cost": _money(per_day_cost, ccy),
        "notes": ("weekly averaged" if weekly_used else None),
    }

def _taxi_estimator(city_fares: Dict[str, Any]) -> Dict[str, Any]:
    tx = (city_fares or {}).get("taxi") or {}
    base = tx.get("base"); per_km = tx.get("per_km"); per_min = tx.get("per_min")
    ccy = tx.get("currency")

    def _estimate(distance_km: float, minutes: float) -> Optional[Dict[str, Any]]:
        if base is None and per_km is None and per_min is None:
            return None
        total = 0.0
        if base is not None: total += float(base)
        if per_km is not None and distance_km is not None: total += float(per_km) * float(distance_km)
        if per_min is not None and minutes is not None: total += float(per_min) * float(minutes)
        return _money(round(total, 2), ccy)

    examples = {
        "short_city_hop": _estimate(3.0, 10.0),  # ~3 km, 10 min
        "airport_like":   _estimate(25.0, 45.0), # ~25 km, 45 min
    }

    return {
        "formula": {"base": base, "per_km": per_km, "per_min": per_min, "currency": ccy},
        "examples": examples,
    }

def _poi_entry_costs(pois: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for p in pois:
        out.append({
            "name": p.get("name"),
            "entry": p.get("price") or None,   # expect Money or None from POI node
        })
    return out

def _lodging_placeholder(req: Dict[str, Any], city: str, nights: int) -> Dict[str, Any]:
    """
    Uses (optional) request.lodging.per_city[city] as Money; else falls back to a default.
    The default currency tries to inherit from transit currency for the city.
    """
    per_city = ((req.get("lodging") or {}).get("per_city") or {}).get(city) or {}
    amt = per_city.get("amount"); ccy = per_city.get("currency")

    if amt is None:
        # simple default per-night heuristic
        # (feel free to tweak; keeping it deterministic for MVP)
        amt = 120.0
    if not ccy:
        # try to inherit currency from fares if available
        tr = ((req.get("city_fares") or {}).get(city) or {}).get("transit") or {}
        ccy = _first_currency(
            (tr.get("single") or {}).get("currency"),
            (tr.get("day_pass") or {}).get("currency"),
            (tr.get("weekly_pass") or {}).get("currency"),
        ) or "USD"

    return {
        "per_night": _money(float(amt), ccy),
        "nights": nights,
        "total": _money(round(float(amt) * float(max(1, nights)), 2), ccy),
        "note": "placeholder",
    }


# --------------------------- main node ---------------------------

def discovery_and_cost(state: AppState) -> AppState:
    """
    Combines #7 Discovery_Join and #8 Cost_Inference.

    Inputs (state.request):
      - cities: [...]
      - dates: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}   (optional; used for nights & weekly decision)
      - poi_results OR pois_by_city
      - city_fares
      - intercity
      - restaurants (optional)
      - restaurant_names (optional)
      - assumptions (optional): {"rides_per_day": int}
      - lodging.per_city (optional): { city: {amount, currency} }

    Output (state.request["discovery"]):
      {
        "cities": {
          "<City>": {
            "pois": [ {name, price|null, hours|null, sources[]}, ... ],
            "fares": { transit:{single,day_pass,weekly_pass,sources[]}, taxi:{...} },
            "restaurants": { "links": [...], "names": [...] },
            "costs": {
              "transit": { rides_per_day, break_even_rides_for_day_pass, per_day_choice, per_day_cost, notes? },
              "taxi":    { formula: {...}, examples: {...} },
              "lodging": { per_night, nights, total, note },
              "poi_entry": [ {name, entry}, ... ]
            }
          }, ...
        },
        "hops": <copy of intercity>
      }
    """
    req, logs = state.request, state.logs or []
    state.meta = state.meta or {}

    cities = req.get("cities") or []
    # print(f"this is cities: {cities}")
    if not cities:
        state.meta["requires_input"] = {"field": "cities", "message": "No cities provided"}
        state.logs = logs; return state

    start, end = _coerce_dates(req.get("dates"))
    # print(f"this is start: {start}")
    # print(f"this is end: {end}")
    rides_per_day = int(((req.get("assumptions") or {}).get("rides_per_day")) or 4)
    nights = _days_between_iso(start, end)

    out: Dict[str, Any] = {"cities": {}, "hops": (req.get("intercity") or {})}

    for city in cities:
        pois = _collect_pois(req, city)
        fares = _collect_city_fares(req, city)
        links, names = _collect_restaurants(req, city)

        # cost inference
        transit_costs = _infer_transit_costs(fares, rides_per_day=rides_per_day, stay_days=nights)
        taxi_costs    = _taxi_estimator(fares)
        lodging_costs = _lodging_placeholder(req, city, nights=nights)
        poi_costs     = _poi_entry_costs(pois)

        out["cities"][city] = {
            "pois": pois,
            "fares": fares,
            "restaurants": {"links": links, "names": names},
            "costs": {
                "transit": transit_costs,
                "taxi": taxi_costs,
                "lodging": lodging_costs,
                "poi_entry": poi_costs,
            },
        }
        # print(f"this is out: {out}")
        logs.append(
            f"Discovery+Cost[{city}]: pois={len(pois)} links={len(links)} names={len(names)} "
            f"transit_choice={transit_costs.get('per_day_choice')}"
        )

    req["discovery"] = out
    state.request, state.logs = req, logs
    return state



