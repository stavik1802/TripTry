# === FILE: app/graph/nodes/geocost_assembler.py ===
from __future__ import annotations
import math, hashlib
from typing import Any, Dict, List, Optional, Tuple

# If you don't have a formal AppState, this will still import; in tests you can stub it.
try:
    from app.graph.state import AppState
except Exception:
    class AppState:  # minimal stub
        def __init__(self, request: Dict[str, Any], logs: List[str] = None, meta: Dict[str, Any] = None):
            self.request = request
            self.logs = logs or []
            self.meta = meta or {}

# ------------------- Tunables (MVP constants) -------------------
# Fallback distances when coordinates are missing (buckets)
BUCKET_KM = {
    "xs": 0.9,   # same neighborhood
    "s":  2.2,   # short hop
    "m":  5.5,   # medium cross-town
    "l":  9.0,   # long cross-town
    "xl": 14.0,  # far edge-to-edge
}

# Small local hop assumed when going to a restaurant for meals
MEAL_LOCAL_KM = 0.8  # ~10 min walk at ~4.8 km/h

# Speed ranges (km/h). We draw a deterministic value per edge within these ranges
WALK_KMH_RANGE    = (4.0, 5.2)
TRANSIT_KMH_RANGE = (18.0, 25.0)
TAXI_KMH_RANGE    = (22.0, 28.0)

# Transit extras
TRANSIT_WAIT_MIN_RANGE = (6, 12)  # draw a deterministic wait/transfer buffer per hop

# Default POI window/dwell if none provided
DEFAULT_POI_OPEN_MIN  = 9*60    # 09:00
DEFAULT_POI_CLOSE_MIN = 18*60   # 18:00
DEFAULT_POI_DWELL_MIN = 60      # 60 minutes baseline

# ------------------- Small helpers -------------------
def _money(amount: Optional[float], currency: Optional[str]) -> Optional[Dict[str, Any]]:
    if amount is None or currency is None:
        return None
    return {"amount": round(float(amount), 2), "currency": str(currency).upper()}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    try:
        from math import radians, sin, cos, asin, sqrt
        R = 6371.0088
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c
    except Exception:
        return BUCKET_KM["m"]


def _mins_for(distance_km: float, kmh: float, extra_min: float = 0.0) -> int:
    if distance_km is None or kmh <= 0:
        return 0
    return int(round((distance_km / kmh) * 60.0 + extra_min))


def _get_latlon(p: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    lat = p.get("lat")
    lon = p.get("lon", p.get("lng"))
    try:
        if lat is None or lon is None:
            return None
        return (float(lat), float(lon))
    except Exception:
        return None


def _poi_window(p: Dict[str, Any]) -> Tuple[int, int]:
    open_min  = p.get("open_min",  DEFAULT_POI_OPEN_MIN)
    close_min = p.get("close_min", DEFAULT_POI_CLOSE_MIN)
    try:
        return int(open_min), int(close_min)
    except Exception:
        return DEFAULT_POI_OPEN_MIN, DEFAULT_POI_CLOSE_MIN


def _poi_dwell(p: Dict[str, Any]) -> int:
    dw = p.get("dwell_min")
    try:
        return int(dw) if dw is not None else DEFAULT_POI_DWELL_MIN
    except Exception:
        return DEFAULT_POI_DWELL_MIN


def _city_centroid(cblob: Dict[str, Any]) -> Optional[Tuple[float,float]]:
    c = (cblob.get("centroid") or cblob.get("center") or cblob.get("coords") or {})
    lat = c.get("lat")
    lon = c.get("lon", c.get("lng"))
    try:
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)
    except Exception:
        return None


def _det_hash(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:12], 16)  # 48-bit chunk is plenty


def _bucket_for(a_id: str, b_id: str, city: str) -> Tuple[float, str]:
    """Deterministic short/medium/long buckets when coords missing."""
    h = _det_hash(a_id, b_id, city)
    pick = h % 10
    if pick <= 1:
        return BUCKET_KM["xs"], "bucket_xs"
    if pick <= 4:
        return BUCKET_KM["s"],  "bucket_s"
    if pick <= 7:
        return BUCKET_KM["m"],  "bucket_m"
    if pick == 8:
        return BUCKET_KM["l"],  "bucket_l"
    return BUCKET_KM["xl"], "bucket_xl"


def _pair_distance_km(A: Dict[str, Any], B: Dict[str, Any], cblob: Dict[str, Any], city: str) -> Tuple[float, str]:
    a = _get_latlon(A); b = _get_latlon(B)
    if a and b:
        return _haversine_km(a[0], a[1], b[0], b[1]), "haversine"
    # try centroid-assisted estimate if one side is missing
    cen = _city_centroid(cblob)
    if cen and a and not b:
        # approx other side as centroid; inflate slightly
        return _haversine_km(a[0], a[1], cen[0], cen[1]) * 1.25, "centroid_one_missing"
    if cen and b and not a:
        return _haversine_km(b[0], b[1], cen[0], cen[1]) * 1.25, "centroid_one_missing"
    # both missing (or no centroid) → bucket distance (deterministic)
    return _bucket_for(A["id"], B["id"], city)


def _transit_edge_cost_ccy(city_blob: Dict[str, Any]) -> Tuple[Optional[float], Optional[str], str]:
    """
    If day/weekly pass chosen for this city, marginal edge cost is 0.
    Otherwise use single fare amount if available.
    """
    costs = (city_blob.get("costs") or {}).get("transit") or {}
    choice = costs.get("per_day_choice")
    per_day_cost = costs.get("per_day_cost") or {}
    fares = (city_blob.get("fares") or {}).get("transit") or {}
    single = fares.get("single") or {}

    if choice in ("day_pass", "weekly_pass"):
        return 0.0, single.get("currency") or per_day_cost.get("currency"), "pass_included"
    if single.get("amount") is not None:
        return float(single["amount"]), single.get("currency"), "single_fare"
    # unknown
    return 0.0, None, "unknown"


def _taxi_formula(city_blob: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
    tx = (city_blob.get("fares") or {}).get("taxi") or {}
    return tx.get("base"), tx.get("per_km"), tx.get("per_min"), tx.get("currency")


def _speed_from_range(rng: Tuple[float,float], key: str) -> float:
    """Deterministic speed selection inside a range based on a key."""
    low, high = rng
    span = max(0.0, high - low)
    if span == 0:
        return low
    h = _det_hash(key)
    frac = (h % 10_000) / 10_000.0  # [0,1)
    return low + frac * span


def _wait_from_range(rng: Tuple[int,int], key: str) -> int:
    low, high = rng
    if low >= high:
        return low
    h = _det_hash(key)
    return low + (h % (high - low + 1))

# ------------------- Main node -------------------

def geocost_assembler(state: AppState) -> AppState:
    """
    Reads request['discovery'] and writes request['geocost'] per city.
    Nodes: hotel + POIs + (Breakfast/Lunch/Dinner as time blocks)
    Edges: complete graph; meal edges use a small local hop distance (MEAL_LOCAL_KM).
    Travel times now come from a simple speed model with deterministic variability per edge.
    When coordinates are missing, distances are derived from city centroid or from short/med/long buckets.
    """
    req, logs = state.request, state.logs or []
    state.meta = state.meta or {}
    disc = req.get("discovery") or {}
    cities = list((disc.get("cities") or {}).keys())
    if not cities:
        state.meta["requires_input"] = {"field": "discovery", "message": "discovery blob missing"}
        state.logs = logs; return state

    out: Dict[str, Any] = {}

    for city in cities:
        cblob = (disc["cities"] or {}).get(city) or {}
        pois  = cblob.get("pois") or []

        # --- Build nodes ---
        nodes: List[Dict[str, Any]] = []
        id_map: Dict[str, int] = {}

        # 0) Hotel (assume city-center hotel; coords optional)
        hotel = {"id": "H", "type": "hotel", "name": f"{city} Hotel", "open_min": 6*60, "close_min": 23*60, "dwell_min": 0}
        # pass through centroid as hotel coords if provided
        cen = _city_centroid(cblob)
        if cen:
            hotel.update({"lat": cen[0], "lon": cen[1]})
        nodes.append(hotel); id_map["H"] = 0

        # 1) POIs
        for i, p in enumerate(pois, start=1):
            nm = (p.get("name") or f"POI {i}").strip()
            open_min, close_min = _poi_window(p)
            dwell_min = _poi_dwell(p)
            node = {
                "id": f"P{i}",
                "type": "poi",
                "name": nm,
                "open_min": open_min,
                "close_min": close_min,
                "dwell_min": dwell_min,
                # pass through coords if present
                **({ "lat": p.get("lat"), "lon": p.get("lon", p.get("lng")) } if _get_latlon(p) else {}),
            }
            nodes.append(node)
            id_map[node["id"]] = len(nodes) - 1

        # 2) Meals
        MEAL_SLOTS = [
            {"id": "MB", "name": "Breakfast", "open_min": 7*60,  "close_min": 10*60+30, "dwell_min": 45},
            {"id": "ML", "name": "Lunch",     "open_min": 12*60, "close_min": 14*60+30, "dwell_min": 45},
            {"id": "MD", "name": "Dinner",    "open_min": 18*60, "close_min": 21*60+30, "dwell_min": 45},
        ]
        for m in MEAL_SLOTS:
            node = {
                "id": m["id"],
                "type": "meal",
                "name": m["name"],
                "open_min": m["open_min"],
                "close_min": m["close_min"],
                "dwell_min": m["dwell_min"],
            }
            nodes.append(node); id_map[node["id"]] = len(nodes) - 1

        # --- Edge costs/time model ---
        # Transit marginal cost per edge
        transit_unit_cost, transit_ccy, _note = _transit_edge_cost_ccy(cblob)
        base, per_km, per_min, taxi_ccy = _taxi_formula(cblob)

        def edge_payload(A: Dict[str, Any], B: Dict[str, Any]) -> Dict[str, Any]:
            # Deterministic per-edge speeds + waits
            edge_key = f"{city}:{A['id']}->{B['id']}"
            v_walk   = _speed_from_range(WALK_KMH_RANGE,   edge_key+":walk")
            v_trans  = _speed_from_range(TRANSIT_KMH_RANGE,edge_key+":transit")
            v_taxi   = _speed_from_range(TAXI_KMH_RANGE,   edge_key+":taxi")
            t_wait   = _wait_from_range(TRANSIT_WAIT_MIN_RANGE, edge_key+":wait")

            # Meal edges: assume a small local hop (MEAL_LOCAL_KM), not zero
            if A["type"] == "meal" or B["type"] == "meal":
                d_km = MEAL_LOCAL_KM
                walk_min    = _mins_for(d_km, v_walk, 0)
                transit_min = _mins_for(d_km, v_trans, t_wait)
                taxi_min    = _mins_for(d_km, v_taxi, 0)

                t_cost = transit_unit_cost or 0.0
                taxi_total = 0.0
                if base is not None:    taxi_total += float(base)
                if per_km is not None:  taxi_total += float(per_km) * float(d_km)
                if per_min is not None: taxi_total += float(per_min) * float(taxi_min)

                return {
                    "walk":    {"min": int(walk_min),    "cost": _money(0.0, transit_ccy or taxi_ccy)},
                    "transit": {"min": int(transit_min), "cost": _money(t_cost, transit_ccy)},
                    "taxi":    {"min": int(taxi_min),    "cost": _money(round(taxi_total, 2), taxi_ccy)},
                    "distance_km": round(d_km, 2),
                    "quality": "assumed_local_meal"
                }

            # Distance
            d_km, quality = _pair_distance_km(A, B, cblob, city)

            walk_min    = _mins_for(d_km, v_walk, 0)
            transit_min = _mins_for(d_km, v_trans, t_wait)
            taxi_min    = _mins_for(d_km, v_taxi, 0)

            # Transit cost: pass-included or single fare
            t_cost = transit_unit_cost or 0.0

            # Taxi cost formula
            taxi_total = 0.0
            if base is not None:    taxi_total += float(base)
            if per_km is not None:  taxi_total += float(per_km) * float(d_km)
            if per_min is not None: taxi_total += float(per_min) * float(taxi_min)

            return {
                "walk":    {"min": int(walk_min),    "cost": _money(0.0, transit_ccy or taxi_ccy)},
                "transit": {"min": int(transit_min), "cost": _money(t_cost, transit_ccy)},
                "taxi":    {"min": int(taxi_min),    "cost": _money(round(taxi_total, 2), taxi_ccy)},
                "distance_km": round(d_km, 2),
                "quality": quality
            }

        # --- Build complete graph edges (undirected; store a<b) ---
        edges: List[Dict[str, Any]] = []
        N = len(nodes)
        for ai in range(N):
            for bi in range(ai + 1, N):
                A, B = nodes[ai], nodes[bi]
                payload = edge_payload(A, B)
                edges.append({
                    "a": A["id"], "b": B["id"],
                    **payload
                })

        # --- Assemble city geocost ---
        out[city] = {
            "nodes": nodes,
            "edges": edges,
            "assumptions": {
                "distance_mode": "haversine/centroid/buckets",
                "buckets_km": BUCKET_KM,
                "speed_ranges_kmh": {
                    "walk": WALK_KMH_RANGE,
                    "transit": TRANSIT_KMH_RANGE,
                    "taxi": TAXI_KMH_RANGE,
                },
                "transit_wait_min_range": TRANSIT_WAIT_MIN_RANGE,
                "meal_local_km": MEAL_LOCAL_KM,
            },
        }
        logs.append(f"GeoCost[{city}]: nodes={len(nodes)} edges={len(edges)}; model=speed_ranges;buckets;centroid")

    req["geocost"] = out
    state.request, state.logs = req, logs
    return state

