# trip_maker.py

from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Try to use your AppState; if not available, a tiny stub
try:
    from app.graph.state import AppState
except Exception:
    @dataclass
    class AppState:
        request: Dict[str, Any]
        logs: List[str] = field(default_factory=list)
        meta: Dict[str, Any] = field(default_factory=dict)

# Import your greedy optimizer
try:
    from app.graph.nodes.optimizer_helper_tool import itinerary_optimizer_greedy
except Exception as e:
    raise RuntimeError("itinerary_optimizer_greedy not importable. Ensure it's in app.graph.nodes.") from e

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None  # graceful degrade; times will be naive


# -------- Defaults (you can override via request["meal_prices"]) --------
MEAL_DEFAULTS = {
    "MB": 8.0,   # Breakfast
    "ML": 15.0,  # Lunch
    "MD": 25.0,  # Dinner
}
MEAL_ID_TO_NAME = {"MB": "Breakfast", "ML": "Lunch", "MD": "Dinner"}

# -------- Intercity scheduling defaults --------
DEFAULT_DAY_START = "09:00"
DEFAULT_DAY_END   = "20:30"
DEFAULT_DEP_BUFFER_MIN = 120
DEFAULT_ARR_BUFFER_MIN = 90
LATE_ARRIVAL_CUTOFF_HOUR = 22        # 22:00 local considered late-night
MIN_START_AFTER_LATE_ARR = "11:00"   # first-day earliest start if late arrival and overnight_ok=False


# ----------------- Helpers: dates & nights -----------------

def _nights_total(dates: Dict[str, str]) -> int:
    if not dates:
        return 1
    try:
        d0 = date.fromisoformat(dates["start"][:10])
        d1 = date.fromisoformat(dates["end"][:10])
        return max(1, (d1 - d0).days)
    except Exception:
        return 1


def _ensure_nights_by_city(req: Dict[str, Any]) -> Dict[str, int]:
    cities: List[str] = req.get("cities") or []
    dates: Dict[str, str] = req.get("dates") or {}
    n_trip = _nights_total(dates)
    nb = req.get("nights_by_city")
    if isinstance(nb, dict) and sum(nb.get(c, 0) for c in cities) == n_trip:
        return nb
    # Even split as fallback
    if not cities:
        return {}
    base, rem = divmod(n_trip, len(cities))
    out = {c: base for c in cities}
    for i in range(rem):
        out[cities[i]] += 1
    return out


def _slice_dates(d0: date, nights: int) -> Tuple[date, date]:
    """Return (start_date, end_date) where nights = (end - start).days"""
    return d0, d0 + timedelta(days=nights)


# ---- New helpers to recover missing inputs ----

def _coerce_cities(req: Dict[str, Any]) -> List[str]:
    """Return cities; if absent, derive from geocost or discovery."""
    cities = list(req.get("cities") or [])
    if cities:
        req["cities"] = cities
        return cities

    gc = req.get("geocost") or {}
    if isinstance(gc, dict) and gc:
        cities = list(gc.keys())

    if not cities:
        disc_cities = (req.get("discovery") or {}).get("cities") or {}
        if isinstance(disc_cities, dict) and disc_cities:
            cities = list(disc_cities.keys())

    req["cities"] = cities
    return cities


def _ensure_dates(req: Dict[str, Any], cities: List[str]) -> Dict[str, str]:
    """
    Ensure req['dates'] exists. If missing, synthesize:
    - total_nights = preferences.duration_days - 1 (if provided), else 2 * len(cities) (min 2)
    - start = today (or anchor_start_date if provided)
    - end = start + total_nights
    Also sets req['nights_by_city'] to an even split of total_nights.
    """
    dates = req.get("dates") or {}
    if dates.get("start") and dates.get("end"):
        return dates

    prefs = req.get("preferences") or {}
    # If the user (or upstream) gave duration_days, use it. Otherwise 2 nights per city, min 2.
    dur_hint = req.get("duration_days") or prefs.get("duration_days")
    try:
        total_nights = max(1, int(dur_hint) - 1) if dur_hint is not None else max(2, 2 * max(1, len(cities)))
    except Exception:
        total_nights = max(2, 2 * max(1, len(cities)))

    anchor = (req.get("anchor_start_date") or date.today().isoformat())[:10]
    d0 = date.fromisoformat(anchor)
    dates = {"start": d0.isoformat(), "end": (d0 + timedelta(days=total_nights)).isoformat()}
    req["dates"] = dates

    # Even split nights across cities to keep the optimizer sane
    if cities:
        base, rem = divmod(total_nights, len(cities))
        nb = {c: base for c in cities}
        for i in range(rem):
            nb[cities[i]] += 1
        req["nights_by_city"] = nb

    return dates


def _normalize_intercity(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept either {'hops':[...]} or a pre-keyed dict.
    Return a dict keyed 'A -> B' so the scheduler can pick it up.
    """
    raw = req.get("intercity") or {}
    if isinstance(raw, dict) and "hops" in raw and isinstance(raw["hops"], list):
        hops = {}
        for h in raw["hops"]:
            a, b = (h.get("from") or "").strip(), (h.get("to") or "").strip()
            if a and b:
                hops[f"{a} -> {b}"] = h
        return hops
    # already a dict (or empty): pass through
    return raw if isinstance(raw, dict) else {}


# ----------------- Money helpers -----------------

def _money_add(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not a and not b:
        return None
    if a and not b:
        return {"amount": round(float(a["amount"]), 2), "currency": a["currency"]}
    if b and not a:
        return {"amount": round(float(b["amount"]), 2), "currency": b["currency"]}
    if a and b and a.get("currency") == b.get("currency"):
        return {"amount": round(float(a["amount"]) + float(b["amount"]), 2), "currency": a["currency"]}
    # different currencies → keep 'a' (MVP)
    return {"amount": round(float(a["amount"]), 2), "currency": a["currency"]}


def _sum_money_list(lst: List[Optional[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    out = None
    for m in lst:
        if m:
            out = _money_add(out, m)
    return out


def _money(amount: Optional[float], ccy: Optional[str]) -> Optional[Dict[str, Any]]:
    if amount is None or ccy is None:
        return None
    return {"amount": round(float(amount), 2), "currency": ccy}


def _money_amt(m: Optional[Dict[str, Any]]) -> Optional[float]:
    try:
        return None if not m else float(m.get("amount"))
    except Exception:
        return None


# ----------------- Timezone & intercity helpers -----------------

def _parse_hhmm(s: Optional[str], fallback: str) -> time:
    s = (s or fallback).strip()
    try:
        hh, mm = s.split(":")
        return time(hour=int(hh), minute=int(mm))
    except Exception:
        fhh, fmm = fallback.split(":")
        return time(hour=int(fhh), minute=int(fmm))


def _city_tz(req: Dict[str, Any], city: str) -> Optional[ZoneInfo]:
    tzmap = (req.get("timezones_by_city") or {})
    tzname = tzmap.get(city)
    if tzname and ZoneInfo:
        try:
            return ZoneInfo(tzname)
        except Exception:
            return None
    return None


def _hop_meta(hop: Dict[str, Any], mode: str) -> Tuple[int, Optional[Dict[str, Any]]]:
    """Return (duration_min, price). Falls back by mode if duration missing."""
    x = hop.get(mode) or {}
    dur = x.get("duration_min")
    if not isinstance(dur, (int, float)):
        dur = {"flight": 720, "rail": 240, "bus": 300}.get(mode, 180)  # sensible defaults
    return int(dur), (x.get("price") or None)


def _choose_intercity_mode(hop: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
    if not hop:
        return ("", None)
    cands = []
    for mode in ("rail", "bus", "flight"):
        x = hop.get(mode) or {}
        price = x.get("price") or {}
        amt, ccy = price.get("amount"), price.get("currency")
        if isinstance(amt, (int, float)) and ccy:
            cands.append((mode, float(amt), price))
    if cands:
        cands.sort(key=lambda t: t[1])
        return (cands[0][0], cands[0][2])
    rec = hop.get("recommended")
    if rec and isinstance(rec, str):
        price = ((hop.get(rec) or {}).get("price") or None)
        return (rec, price)
    return ("", None)


def _schedule_intercity(req: Dict[str, Any], from_city: str, to_city: str, hop: Dict[str, Any], dep_day: date) -> Dict[str, Any]:
    prefs = req.get("preferences") or {}
    day_start = _parse_hhmm(prefs.get("day_start_local"), DEFAULT_DAY_START)
    dep_buffer = int(prefs.get("air_departure_buffer_min", DEFAULT_DEP_BUFFER_MIN))
    arr_buffer = int(prefs.get("air_arrival_buffer_min", DEFAULT_ARR_BUFFER_MIN))

    mode, base_price = _choose_intercity_mode(hop)
    if not mode:
        mode = hop.get("recommended") or "flight"

    dur_min, price = _hop_meta(hop, mode)
    if not price:
        price = base_price

    # Default departure: transfer day at (day_start + dep_buffer/60 rounded) local time at FROM city
    tz_from = _city_tz(req, from_city)
    tz_to   = _city_tz(req, to_city)

    dep_base_tm = (datetime.combine(dep_day, day_start))
    if tz_from:
        dep_base_tm = dep_base_tm.replace(tzinfo=tz_from)

    # Add buffer before takeoff
    dep_local = dep_base_tm + timedelta(minutes=dep_buffer)
    arr_local = dep_local + timedelta(minutes=dur_min)
    if tz_from and tz_to:
        # Convert arrival instant into destination timezone
        arr_local = arr_local.astimezone(tz_to)

    return {
        "date": dep_day.isoformat(),
        "from": from_city,
        "to": to_city,
        "mode": mode,
        "duration_min": int(dur_min),
        "dep_local": dep_local.isoformat(),
        "arr_local": arr_local.isoformat(),
        "tz_from": getattr(tz_from, 'key', None),
        "tz_to": getattr(tz_to, 'key', None),
        "travel_cost": price,
    }


def _first_day_start_after_arrival(req: Dict[str, Any], city: str, city_start_day: date, intercity_block: Dict[str, Any]) -> str:
    """Return ISO string for next city's start, respecting arrival + buffer and overnight rules."""
    prefs = req.get("preferences") or {}
    day_start = _parse_hhmm(prefs.get("day_start_local"), DEFAULT_DAY_START)
    overnight_ok = bool(prefs.get("overnight_ok", True))
    arr_buffer = int(prefs.get("air_arrival_buffer_min", DEFAULT_ARR_BUFFER_MIN))

    tz = _city_tz(req, city)
    start_dt = datetime.combine(city_start_day, day_start)
    if tz:
        start_dt = start_dt.replace(tzinfo=tz)

    # Arrival instant in destination timezone
    try:
        arr_dt = datetime.fromisoformat(intercity_block["arr_local"])  # already tz-aware if tz_to present
    except Exception:
        arr_dt = start_dt

    window_start = max(start_dt, arr_dt + timedelta(minutes=arr_buffer))

    # If late-night arrival and overnight not ok → don't start earlier than 11:00
    late_cut = time(hour=LATE_ARRIVAL_CUTOFF_HOUR, minute=0)
    min_after_late = _parse_hhmm(MIN_START_AFTER_LATE_ARR, MIN_START_AFTER_LATE_ARR)

    if not overnight_ok:
        if (arr_dt.timetz().hour if hasattr(arr_dt, 'timetz') else arr_dt.time().hour) >= LATE_ARRIVAL_CUTOFF_HOUR:
            if window_start.time() < min_after_late:
                window_start = window_start.replace(hour=min_after_late.hour, minute=min_after_late.minute, second=0, microsecond=0)

    return window_start.isoformat()


# ----------------- Planner sub-call helpers -----------------

def _make_city_itinerary(state: AppState, city: str, geocost_city: Dict[str, Any], start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
    sub = AppState(
        request={"geocost": {city: geocost_city}, "dates": {"start": start_iso, "end": end_iso}},
        logs=[], meta={}
    )
    itinerary_optimizer_greedy(sub)
    return sub.request.get("itinerary", {}).get("cities", {}).get(city, [])


def _flip_to_no_taxi(geocost_city: Dict[str, Any]) -> Dict[str, Any]:
    g = deepcopy(geocost_city)
    for e in g.get("edges", []):
        e["taxi"]["min"] = int(e["taxi"]["min"]) + 999
        if e["taxi"]["cost"]:
            e["taxi"]["cost"]["amount"] = float(e["taxi"]["cost"]["amount"]) + 10_000.0
        else:
            e["taxi"]["cost"] = {"amount": 10_000.0, "currency": (e.get("transit", {}).get("cost", {}) or {}).get("currency", "USD")}
    return g


# ----------------- Meal helpers -----------------

def _get_meal_prices(req: Dict[str, Any], target_ccy: str) -> Dict[str, Dict[str, Any]]:
    override = (req.get("meal_prices") or {})
    out: Dict[str, Dict[str, Any]] = {}
    for mid, default_amt in MEAL_DEFAULTS.items():
        name = MEAL_ID_TO_NAME[mid]
        amt = override.get(name, default_amt)
        try:
            amt = float(amt)
        except Exception:
            amt = default_amt
        out[mid] = {"amount": round(amt, 2), "currency": target_ccy}
    return out


def _meals_cost_sum(itin_days: List[Dict[str, Any]], meal_prices: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    out = None
    for day in itin_days:
        for it in (day.get("items") or []):
            if it.get("type") == "meal":
                mid = it.get("node_id")
                price = meal_prices.get(mid)
                if price:
                    out = _money_add(out, price)
    return out


# ----------------- Utilities to attach intercity block into day timeline -----------------

def _ensure_day(day_timeline: List[Dict[str, Any]], date_iso: str, city: str) -> Dict[str, Any]:
    for d in day_timeline:
        if d.get("date") == date_iso and d.get("city") == city:
            return d
    d = {"date": date_iso, "city": city, "items": []}
    day_timeline.append(d)
    return d


# ----------------- Main node -----------------

def trip_orchestrator(state: AppState) -> AppState:
    req, logs = state.request, state.logs or []
    state.meta = state.meta or {}
    # NEW: recover cities / dates if missing (don’t bail early)
    cities = _coerce_cities(req)
    if not cities:
        state.meta["requires_input"] = {"field": "cities", "message": "at least one city required"}
        state.logs = logs
        return state

    dates = _ensure_dates(req, cities)

    prefs = req.get("preferences") or {}
    target_ccy = req.get("target_currency") or "EUR"
    meal_prices = _get_meal_prices(req, target_ccy)

    d0 = date.fromisoformat(dates["start"][:10])
    nights_by_city = _ensure_nights_by_city(req)

    discovery = req.get("discovery") or {}

    geocost   = req.get("geocost") or {}

    # NEW: normalize intercity to a keyed dict regardless of upstream shape
    hops_all  = _normalize_intercity(req)
    budget_caps = req.get("budget_caps") or {}

    # ---- Build per-city spans ----
    day_timeline: List[Dict[str, Any]] = []
    intercity_timeline: List[Dict[str, Any]] = []
    totals_lodging = None
    totals_transit = None
    totals_intercity = None

    cur_date = d0
    city_spans: List[Tuple[str, date, date]] = []
    for city in cities:
        n = int(nights_by_city.get(city, 1))
        c_start, c_end = _slice_dates(cur_date, n)
        city_spans.append((city, c_start, c_end))
        cur_date = c_end  # next city starts on same day (travel day)

    # Plan city by city, inserting intercity with TZ-aware dep/arr between spans
    hop_list = []
    for idx, (city, c_start, c_end) in enumerate(city_spans):
        disc_city = (discovery.get("cities") or {}).get(city) or {}
        g_city    = (geocost or {}).get(city) or {}

        # If there is a previous hop that arrives into THIS city, compute first-day start ISO
        if idx == 0:
            start_iso = datetime.combine(c_start, _parse_hhmm(prefs.get("day_start_local"), DEFAULT_DAY_START))
            tz0 = _city_tz(req, city)
            if tz0:
                start_iso = start_iso.replace(tzinfo=tz0)
            start_iso_s = start_iso.isoformat()
        else:
            prev_city, prev_start, prev_end = city_spans[idx-1]
            hop_key = f"{prev_city} -> {city}"
            hop = (hops_all.get(hop_key) or {})
            intercity_block = _schedule_intercity(req, prev_city, city, hop, prev_end)
            intercity_timeline.append(intercity_block)
            hop_list.append(intercity_block)
            totals_intercity = _money_add(totals_intercity, intercity_block.get("travel_cost"))

            # Insert a visible intercity item into PREV city's last day
            dday = _ensure_day(day_timeline, prev_end.isoformat(), prev_city)
            dday.setdefault("items", []).append({
                "type": "intercity",
                "label": f"{intercity_block['mode'].title()} {prev_city} → {city}",
                "mode": intercity_block['mode'],
                "from": prev_city,
                "to": city,
                "dep_local": intercity_block['dep_local'],
                "arr_local": intercity_block['arr_local'],
                "duration_min": intercity_block['duration_min'],
                "travel_cost": intercity_block.get("travel_cost"),
            })

            # Compute the next city's first-day start (arrival+buffer, overnight rules)
            start_iso_s = _first_day_start_after_arrival(req, city, c_start, intercity_block)

        # Make city itinerary with possibly-late start on day 1
        itin_days = _make_city_itinerary(state, city, g_city, start_iso_s, c_end.isoformat())

        # Attach city + absolute dates to each card; ensure day objects exist in timeline
        cur = c_start
        for day in itin_days:
            if "date" not in day:
                day["date"] = cur.isoformat()
            day.setdefault("city", city)
            _ensure_day(day_timeline, day["date"], city)["items"] = day.get("items", [])
            cur += timedelta(days=1)

        # Transit per-day cost * days
        transit_pd = ((disc_city.get("costs") or {}).get("transit") or {}).get("per_day_cost")
        if transit_pd and isinstance(transit_pd.get("amount"), (int, float)):
            totals_transit = _money_add(
                totals_transit,
                {"amount": float(transit_pd["amount"]) * float((c_end - c_start).days), "currency": transit_pd["currency"]}
            )

        # Lodging total (from discovery costs if present)
        lodging = ((disc_city.get("costs") or {}).get("lodging") or {}).get("total")
        totals_lodging = _money_add(totals_lodging, lodging)

    # Aggregate variable costs from itinerary
    def _itinerary_travel_cost_sum(itin_days: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        out = None
        for day in itin_days:
            for it in (day.get("items") or []):
                c = it.get("travel_cost")
                if c and isinstance(c.get("amount"), (int, float)):
                    out = _money_add(out, c)
        return out

    travel_costs = _itinerary_travel_cost_sum(day_timeline)

    # POI entry costs across all cities
    def _poi_entry_costs_sum(discovery_city: Dict[str, Any], itin_days_for_city: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # First try the old format (costs.poi_entry)
        entry_map: Dict[str, Optional[Dict[str, Any]]] = {}
        for e in (discovery_city.get("costs") or {}).get("poi_entry", []) or []:
            nm = (e.get("name") or "").strip()
            if nm:
                entry_map[nm] = e.get("entry") or None
        
        # If no costs found in old format, try the new format (pois[].price)
        if not entry_map:
            for poi in (discovery_city.get("pois") or []):
                nm = (poi.get("name") or "").strip()
                price = poi.get("price")
                if nm and price and isinstance(price, dict):
                    # Convert price structure to entry format
                    adult_price = price.get("adult", 0)
                    child_price = price.get("child", 0)
                    currency = price.get("currency", "EUR")
                    
                    # For now, use adult price as the entry cost
                    # TODO: This should be calculated based on actual travelers
                    if adult_price and isinstance(adult_price, (int, float)):
                        entry_map[nm] = {"amount": float(adult_price), "currency": currency}
        
        out = None
        for day in itin_days_for_city:
            for it in (day.get("items") or []):
                if it.get("type") == "poi":
                    nm = (it.get("name") or "").strip()
                    m = entry_map.get(nm)
                    if m and isinstance(m.get("amount"), (int, float)):
                        out = _money_add(out, m)
        return out

    poi_entry_costs = None
    for city in cities:
        poi_entry_costs = _money_add(
            poi_entry_costs,
            _poi_entry_costs_sum((discovery.get("cities") or {}).get(city, {}), [d for d in day_timeline if d.get("city") == city])
        )

    # Meals (fixed per scheduled meal occurrence)
    meals_costs = _meals_cost_sum(day_timeline, meal_prices)

    # Grand total for display
    grand_total = _sum_money_list([totals_lodging, totals_transit, totals_intercity, travel_costs, poi_entry_costs, meals_costs])

    # ---- Budget enforcement (same logic; we don't re-run intercity) ----
    total_cap = budget_caps.get("total")
    include_lodging = budget_caps.get("include_lodging", True)

    def _spend_for_budget(include_lodging_flag: bool,
                          t_lodging, t_transit, t_intercity, t_travel, t_poi, t_meals):
        parts = []
        if include_lodging_flag:
            parts.append(t_lodging)
        parts += [t_transit, t_intercity, t_travel, t_poi, t_meals]
        return _sum_money_list(parts)

    spend_for_budget = _spend_for_budget(include_lodging, totals_lodging, totals_transit, totals_intercity, travel_costs, poi_entry_costs, meals_costs)

    budget_met = True
    attempt_note = None

    if total_cap is not None and spend_for_budget and spend_for_budget.get("currency") == target_ccy:
        if _money_amt(spend_for_budget) is not None and _money_amt(spend_for_budget) > float(total_cap):
            budget_met = False
            attempt_note = "replanned_no_taxi"
            day_timeline2: List[Dict[str, Any]] = []
            totals_transit2 = None
            totals_lodging2 = totals_lodging
            totals_intercity2 = totals_intercity

            for (city, c_start, c_end) in city_spans:
                disc_city = (discovery.get("cities") or {}).get(city) or {}
                g_city    = (geocost or {}).get(city) or {}
                g_no_taxi = _flip_to_no_taxi(g_city)

                # Keep the same start/end we used above (no change to intercity)
                # If this city had a preceding hop, compute start with the same rule
                start_iso_s = None
                for hop in hop_list:
                    if hop["to"] == city:
                        start_iso_s = _first_day_start_after_arrival(req, city, c_start, hop)
                        break
                if not start_iso_s:
                    start_iso_s = datetime.combine(c_start, _parse_hhmm(prefs.get("day_start_local"), DEFAULT_DAY_START)).isoformat()

                itin_days2 = _make_city_itinerary(state, city, g_no_taxi, start_iso_s, c_end.isoformat())

                cur = c_start
                for day in itin_days2:
                    if "date" not in day:
                        day["date"] = cur.isoformat()
                    day.setdefault("city", city)
                    _ensure_day(day_timeline2, day["date"], city)["items"] = day.get("items", [])
                    cur += timedelta(days=1)

                transit_pd = ((disc_city.get("costs") or {}).get("transit") or {}).get("per_day_cost")
                if transit_pd and isinstance(transit_pd.get("amount"), (int, float)):
                    totals_transit2 = _money_add(
                        totals_transit2,
                        {"amount": float(transit_pd["amount"]) * float((c_end - c_start).days), "currency": transit_pd["currency"]}
                    )

            def _itinerary_travel_cost_sum2(itin_days: List[Dict[str, Any]]):
                out = None
                for day in itin_days:
                    for it in (day.get("items") or []):
                        c = it.get("travel_cost")
                        if c and isinstance(c.get("amount"), (int, float)):
                            out = _money_add(out, c)
                return out

            travel_costs2 = _itinerary_travel_cost_sum2(day_timeline2)

            def _poi_entry_costs_sum2(discovery_city: Dict[str, Any], itin_days_for_city: List[Dict[str, Any]]):
                # First try the old format (costs.poi_entry)
                entry_map: Dict[str, Optional[Dict[str, Any]]] = {}
                for e in (discovery_city.get("costs") or {}).get("poi_entry", []) or []:
                    nm = (e.get("name") or "").strip()
                    if nm:
                        entry_map[nm] = e.get("entry") or None
                
                # If no costs found in old format, try the new format (pois[].price)
                if not entry_map:
                    for poi in (discovery_city.get("pois") or []):
                        nm = (poi.get("name") or "").strip()
                        price = poi.get("price")
                        if nm and price and isinstance(price, dict):
                            # Convert price structure to entry format
                            adult_price = price.get("adult", 0)
                            child_price = price.get("child", 0)
                            currency = price.get("currency", "EUR")
                            
                            # For now, use adult price as the entry cost
                            # TODO: This should be calculated based on actual travelers
                            if adult_price and isinstance(adult_price, (int, float)):
                                entry_map[nm] = {"amount": float(adult_price), "currency": currency}
                
                out = None
                for day in itin_days_for_city:
                    for it in (day.get("items") or []):
                        if it.get("type") == "poi":
                            nm = (it.get("name") or "").strip()
                            m = entry_map.get(nm)
                            if m and isinstance(m.get("amount"), (int, float)):
                                out = _money_add(out, m)
                return out

            poi_entry_costs2 = None
            for city in cities:
                poi_entry_costs2 = _money_add(
                    poi_entry_costs2,
                    _poi_entry_costs_sum2((discovery.get("cities") or {}).get(city, {}), [d for d in day_timeline2 if d.get("city") == city])
                )
            meals_costs2 = _meals_cost_sum(day_timeline2, meal_prices)

            spend_for_budget2 = _spend_for_budget(include_lodging, totals_lodging2, totals_transit2, totals_intercity2, travel_costs2, poi_entry_costs2, meals_costs2)

            if spend_for_budget2 and spend_for_budget2.get("currency") == target_ccy and _money_amt(spend_for_budget2) is not None:
                if _money_amt(spend_for_budget2) <= float(total_cap):
                    day_timeline = day_timeline2
                    travel_costs = travel_costs2
                    totals_transit = totals_transit2
                    poi_entry_costs = poi_entry_costs2
                    meals_costs = meals_costs2
                    spend_for_budget = spend_for_budget2
                    budget_met = True
                elif _money_amt(spend_for_budget2) < _money_amt(spend_for_budget):
                    day_timeline = day_timeline2
                    travel_costs = travel_costs2
                    totals_transit = totals_transit2
                    poi_entry_costs = poi_entry_costs2
                    meals_costs = meals_costs2
                    spend_for_budget = spend_for_budget2

    # Convert all costs to target currency for consistency
    def _convert_to_target_currency(cost_dict, target_currency):
        """Convert cost to target currency if different"""
        if not cost_dict or not isinstance(cost_dict, dict):
            return cost_dict
        if cost_dict.get("currency") == target_currency:
            return cost_dict
        # For now, just change the currency (in a real system, you'd do conversion)
        return {"amount": cost_dict.get("amount", 0), "currency": target_currency}
    
    # Convert all costs to target currency
    totals_lodging = _convert_to_target_currency(totals_lodging, target_ccy)
    totals_transit = _convert_to_target_currency(totals_transit, target_ccy)
    totals_intercity = _convert_to_target_currency(totals_intercity, target_ccy)
    travel_costs = _convert_to_target_currency(travel_costs, target_ccy)
    poi_entry_costs = _convert_to_target_currency(poi_entry_costs, target_ccy)
    meals_costs = _convert_to_target_currency(meals_costs, target_ccy)
    
    # Recompute display grand total with final parts
    grand_total = _sum_money_list([totals_lodging, totals_transit, totals_intercity, travel_costs, poi_entry_costs, meals_costs])

    # Assemble trip output
    req["trip"] = {
        "days": day_timeline,
        "intercity": intercity_timeline,  # now includes dep/arr local ISO & duration
        "nights_by_city": nights_by_city,
        "totals": {
            "lodging": totals_lodging,
            "transit": totals_transit,
            "intercity": totals_intercity,
            "travel": travel_costs,
            "poi_entry": poi_entry_costs,
            "meals": meals_costs,
            "grand_total": grand_total,
        },
        "budget": {
            "target_currency": target_ccy,
            "cap_total": budget_caps.get("total"),
            "include_lodging": budget_caps.get("include_lodging", True),
            "met": True if budget_caps.get("total") is None else (budget_met),
            "spend_total": spend_for_budget,
            "note": attempt_note,
            "meal_prices_used": meal_prices,
        }
    }

    # Logging (ensure AUS→TYO style block visible if supplied)
    if intercity_timeline:
        first_hop = intercity_timeline[0]
        logs.append(
            f"Intercity: {first_hop.get('from')}→{first_hop.get('to')} {first_hop.get('mode')} "
            f"{first_hop.get('dep_local')}→{first_hop.get('arr_local')} ({first_hop.get('duration_min')}m)"
        )

    logs.append(
        f"Trip_Orchestrator: days={len(day_timeline)} budget_met={req['trip']['budget']['met']} spend={req['trip']['budget']['spend_total']}"
    )
    state.request, state.logs = req, logs
    return state
