# === FILE: app/graph/nodes/optimizer_helper.py ===
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Try to use your AppState; fall back to a tiny stub for tests.
try:
    from app.graph.state import AppState
except Exception:
    @dataclass
    class AppState:
        request: Dict[str, Any]
        logs: List[str] = field(default_factory=list)
        meta: Dict[str, Any] = field(default_factory=dict)

# ---------- Tunables ----------
DAY_START_MIN = 9 * 60           # 09:00
DAY_END_MIN   = 21 * 60 + 30     # 21:30
MAX_POIS_PER_DAY = 3
MAX_WALK_MIN = 15                # prefer walk if <= 15 minutes
TAXI_FASTER_MARGIN = 10          # if taxi is >=10 min faster than transit (even with pass), pick taxi

MEAL_IDS = ("MB", "ML", "MD")    # Breakfast, Lunch, Dinner

# ---------- Helpers ----------
def _days_between_iso(start: Optional[str], end: Optional[str]) -> int:
    if not start or not end:
        return 1
    from datetime import date
    try:
        d0 = date.fromisoformat(start[:10])
        d1 = date.fromisoformat(end[:10])
        n = (d1 - d0).days
        return max(1, n)
    except Exception:
        return 1


def _money_add(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Add amounts if same currency; otherwise keep first non-null."""
    if not a and not b: return None
    if a and not b: return {"amount": round(float(a["amount"]), 2), "currency": a["currency"]}
    if b and not a: return {"amount": round(float(b["amount"]), 2), "currency": b["currency"]}
    if a and b and a.get("currency") == b.get("currency"):
        return {"amount": round(float(a["amount"]) + float(b["amount"]), 2), "currency": a["currency"]}
    # different currencies? just keep 'a' (MVP)
    return {"amount": round(float(a["amount"]), 2), "currency": a["currency"]}


def _m_amt(m: Optional[Dict[str, Any]]) -> Optional[float]:
    try:
        return None if not m else float(m.get("amount"))
    except Exception:
        return None


def _edge_key(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _build_edge_map(edges: List[Dict[str, Any]]) -> Dict[Tuple[str,str], Dict[str, Any]]:
    return {_edge_key(e["a"], e["b"]): e for e in edges}


def _choose_mode(e: Dict[str, Any]) -> Tuple[str, int, Optional[Dict[str, Any]]]:
    """
    Simple mode choice:
      - If walk <= 15 min -> walk
      - Else if transit cost == 0 and transit time <= taxi time + 10 -> transit
      - Else pick cheaper between transit and taxi when both present, tie -> faster
    Returns: (mode, travel_min, travel_cost_money)
    """
    w = int(e["walk"]["min"])
    t = int(e["transit"]["min"])
    x = int(e["taxi"]["min"])
    tc = e["transit"]["cost"]
    xc = e["taxi"]["cost"]

    if w <= MAX_WALK_MIN:
        # Prefer explicit 0-cost walk currency fallbacks
        ccy = None
        if tc and tc.get("currency"): ccy = tc["currency"]
        elif xc and xc.get("currency"): ccy = xc["currency"]
        else: ccy = "USD"
        return ("walk", w, {"amount": 0.0, "currency": ccy})

    t_amt = _m_amt(tc)
    x_amt = _m_amt(xc)

    if t_amt is not None and t_amt == 0.0 and t <= x + TAXI_FASTER_MARGIN:
        return ("transit", t, tc)

    # If one of them is missing, pick the other
    if t_amt is None and x_amt is not None:
        return ("taxi", x, xc)
    if x_amt is None and t_amt is not None:
        return ("transit", t, tc)

    # Both present: pick cheaper; on tie pick faster
    if t_amt is not None and x_amt is not None:
        if t_amt < x_amt - 1e-6:   # strictly cheaper
            return ("transit", t, tc)
        if x_amt < t_amt - 1e-6:
            return ("taxi", x, xc)
        # equal-ish cost: pick faster
        return ("transit", t, tc) if t <= x else ("taxi", x, xc)

    # Fallback
    return ("transit", t, tc)


def _edge_payload(edge_map, a_id: str, b_id: str) -> Tuple[str, int, Optional[Dict[str, Any]], Dict[str, Any]]:
    e = edge_map.get(_edge_key(a_id, b_id))
    if not e:
        # no edge (shouldn't happen with complete graph) — vary fallback to avoid identical durations
        fake = {"walk": {"min": 12, "cost": {"amount": 0.0, "currency": "USD"}},
                "transit": {"min": 22, "cost": {"amount": 2.5, "currency": "USD"}},
                "taxi": {"min": 14, "cost": {"amount": 10.0, "currency": "USD"}}}
        return ("transit", fake["transit"]["min"], fake["transit"]["cost"], fake)
    mode, tmin, cost = _choose_mode(e)
    return (mode, tmin, cost, e)


def _within_window(start_min: int, dwell_min: int, open_min: int, close_min: int) -> bool:
    return start_min >= open_min and (start_min + dwell_min) <= close_min


def _first_feasible_start(arrival_min: int, dwell_min: int, open_min: int, close_min: int) -> Optional[int]:
    """If arriving before open, wait until open; if after close-dwell, infeasible."""
    start = max(arrival_min, open_min)
    return start if (start + dwell_min) <= close_min else None

# ---------- Core Greedy ----------

def itinerary_optimizer_greedy(state: AppState) -> AppState:
    """
    Inputs:
      - request['geocost'][city] with nodes, edges (from geocost_assembler)
      - request['dates'] for number of days (optional; default = 1)
    Output:
      - request['itinerary'] = { "cities": { city: [ day_cards... ] } }
    """
    req, logs = state.request, state.logs or []
    state.meta = state.meta or {}

    geocost = req.get("geocost") or {}
    if not geocost:
        state.meta["requires_input"] = {"field": "geocost", "message": "geocost missing"}
        state.logs = logs; return state

    # trip length -> number of days
    d_dates = (req.get("dates") or {})
    days_total = _days_between_iso(d_dates.get("start"), d_dates.get("end"))

    out: Dict[str, List[Dict[str, Any]]] = {}

    for city, g in geocost.items():
        nodes: List[Dict[str, Any]] = g.get("nodes", [])
        edges: List[Dict[str, Any]] = g.get("edges", [])
        edge_map = _build_edge_map(edges)

        # index nodes
        by_id = {n["id"]: n for n in nodes}
        hotel_id = "H"
        poi_ids = [n["id"] for n in nodes if n.get("type") == "poi"]
        meal_ids = [n["id"] for n in nodes if n.get("type") == "meal"]

        # sort POIs by (earlier close, then name) to bias greediness
        poi_ids.sort(key=lambda nid: (int(by_id[nid].get("close_min", 18*60)), by_id[nid].get("name","")))

        # prepare meal windows
        meal_info = {mid: (int(by_id[mid]["open_min"]), int(by_id[mid]["close_min"]), int(by_id[mid]["dwell_min"])) for mid in meal_ids}
        # fixed order for meals we try to include each day
        meal_order = [mid for mid in ("MB","ML","MD") if mid in meal_ids]

        # tracking
        remaining_pois = set(poi_ids)
        day_cards: List[Dict[str, Any]] = []

        for day in range(1, max(1, days_total) + 1):
            if not remaining_pois:
                break

            day_start = DAY_START_MIN
            day_end   = DAY_END_MIN
            cur_id    = hotel_id
            cur_time  = day_start
            used_meals = set()
            used_pois  = 0

            items: List[Dict[str, Any]] = []
            travel_cost_total: Optional[Dict[str, Any]] = None

            # Try to schedule breakfast immediately if feasible
            if "MB" in meal_info and "MB" not in used_meals:
                mb_open, mb_close, mb_dwell = meal_info["MB"]
                # travel from hotel to MB
                mode, tmin, cost, _ = _edge_payload(edge_map, cur_id, "MB")
                arr = cur_time + tmin
                start = _first_feasible_start(arr, mb_dwell, mb_open, mb_close)
                if start is not None and (start + mb_dwell) <= day_end:
                    items.append({
                        "node_id": "MB", "type": "meal", "name": by_id["MB"]["name"],
                        "from_id": cur_id, "mode": mode, "travel_min": tmin, "travel_cost": cost,
                        "arrive_min": arr, "start_min": start, "end_min": start + mb_dwell
                    })
                    travel_cost_total = _money_add(travel_cost_total, cost)
                    cur_id, cur_time = "MB", start + mb_dwell
                    used_meals.add("MB")

            def maybe_schedule_meal(mid: str) -> bool:
                nonlocal cur_id, cur_time, travel_cost_total
                if mid not in meal_info or mid in used_meals:
                    return False
                open_m, close_m, dwell_m = meal_info[mid]
                mode, tmin, cost, _ = _edge_payload(edge_map, cur_id, mid)
                arr = cur_time + tmin
                start = _first_feasible_start(arr, dwell_m, open_m, close_m)
                if start is None or (start + dwell_m) > day_end:
                    return False
                # Also check we can still return to hotel after meal
                mode_back, t_back, _c_back, _ = _edge_payload(edge_map, mid, hotel_id)
                if start + dwell_m + t_back > day_end:
                    return False
                items.append({
                    "node_id": mid, "type": "meal", "name": by_id[mid]["name"],
                    "from_id": cur_id, "mode": mode, "travel_min": tmin, "travel_cost": cost,
                    "arrive_min": arr, "start_min": start, "end_min": start + dwell_m
                })
                travel_cost_total = _money_add(travel_cost_total, cost)
                cur_id, cur_time = mid, start + dwell_m
                used_meals.add(mid)
                return True

            # Greedy POI fill
            while used_pois < MAX_POIS_PER_DAY and remaining_pois:
                # If we're around lunchtime and not yet taken, attempt ML first
                if "ML" in meal_info and "ML" not in used_meals and cur_time >= meal_info["ML"][0] - 20 and cur_time <= meal_info["ML"][1]:
                    maybe_schedule_meal("ML")

                # Evaluate candidates
                best = None  # (finish_time, travel_min, start_time, next_id, mode, cost)
                for nid in list(remaining_pois):
                    n = by_id[nid]
                    dwell = int(n.get("dwell_min", 60))
                    open_m = int(n.get("open_min", 9*60))
                    close_m = int(n.get("close_min", 18*60))

                    mode, tmin, cost, _ = _edge_payload(edge_map, cur_id, nid)
                    arr = cur_time + tmin
                    start = _first_feasible_start(arr, dwell, open_m, close_m)
                    if start is None:
                        continue
                    endv = start + dwell

                    # ensure return to hotel is possible after visiting
                    mode_back, t_back, _c_back, _ = _edge_payload(edge_map, nid, hotel_id)
                    if endv + t_back > day_end:
                        continue

                    # pick the one with minimal travel time (tmin); tie-break earlier close
                    cand = (endv, tmin, start, nid, mode, cost, close_m)
                    if (best is None) or (tmin < best[1]) or (tmin == best[1] and close_m < best[6]):
                        best = cand

                if not best:
                    break  # nothing feasible

                endv, tmin, start, nid, mode, cost, _close = best
                # commit the POI
                items.append({
                    "node_id": nid, "type": "poi", "name": by_id[nid]["name"],
                    "from_id": cur_id, "mode": mode, "travel_min": tmin, "travel_cost": cost,
                    "arrive_min": cur_time + tmin, "start_min": start, "end_min": endv
                })
                travel_cost_total = _money_add(travel_cost_total, cost)
                cur_id, cur_time = nid, endv
                remaining_pois.discard(nid)
                used_pois += 1

                # opportunistic lunch if we just crossed noon
                if "ML" in meal_info and "ML" not in used_meals and cur_time < day_end:
                    maybe_schedule_meal("ML")

                # Stop if next addition obviously cannot fit (guard)
                mode_back, t_back, _c_back, _ = _edge_payload(edge_map, cur_id, hotel_id)
                if cur_time + t_back > day_end:
                    break

            # Try to add dinner before going back
            if "MD" in meal_info and "MD" not in used_meals:
                maybe_schedule_meal("MD")

            # Return to hotel
            mode_back, t_back, c_back, _ = _edge_payload(edge_map, cur_id, hotel_id)
            if cur_id != hotel_id and cur_time + t_back <= day_end:
                items.append({
                    "node_id": hotel_id, "type": "hotel", "name": "Hotel return",
                    "from_id": cur_id, "mode": mode_back, "travel_min": t_back, "travel_cost": c_back,
                    "arrive_min": cur_time + t_back, "start_min": cur_time + t_back, "end_min": cur_time + t_back
                })
                travel_cost_total = _money_add(travel_cost_total, c_back)
                cur_id, cur_time = hotel_id, cur_time + t_back

            day_cards.append({
                "day": day,
                "city": city,
                "day_start_min": day_start,
                "day_end_min": day_end,
                "items": items,
                "totals": {
                    "travel_cost": travel_cost_total,
                    "poi_count": sum(1 for it in items if it["type"] == "poi"),
                    "meal_count": sum(1 for it in items if it["type"] == "meal"),
                },
                "notes": [],
            })

        out[city] = day_cards
        # Quick sanity: capture a sample of the edge times to ensure diversity (no flat 58 everywhere)
        if edges:
            mins = sorted({(e["walk"]["min"], e["transit"]["min"], e["taxi"]["min"]) for e in edges})
            logs.append(f"Greedy[{city}]: days={len(day_cards)} unique_edge_time_triplets={len(mins)}")
        else:
            logs.append(f"Greedy[{city}]: days={len(day_cards)} (no edges)")

    req["itinerary"] = {"cities": out}
    state.request, state.logs = req, logs
    return state