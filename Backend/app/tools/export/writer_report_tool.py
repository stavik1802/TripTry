"""
Writer Report Tool for TripPlanner Multi-Agent System

This tool generates comprehensive trip reports in multiple formats including JSON,
markdown overview, and detailed daily summaries. It processes completed trip data
and creates formatted reports for users.

Key features:
- Multi-format report generation (JSON, markdown, daily summaries)
- Comprehensive cost breakdown and analysis
- Day-by-day itinerary formatting
- Budget tracking and validation
- Currency normalization and conversion

The tool creates detailed, user-friendly reports that summarize the complete
trip plan with costs, schedules, and recommendations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

# AppState shim
try:
    from app.tools.tools_utils.state import AppState
except Exception:
    @dataclass
    class AppState:
        request: Dict[str, Any]
        logs: List[str] = field(default_factory=list)
        meta: Dict[str, Any] = field(default_factory=dict)

# ---------- small helpers ----------
def _hm(mins: Optional[int]) -> str:
    if mins is None: return "--:--"
    h, m = divmod(int(mins), 60)
    return f"{h:02d}:{m:02d}"

def _money_str(m: Optional[Dict[str, Any]]) -> str:
    if not m: return "-"
    try:
        return f"{float(m['amount']):.2f} {m['currency']}"
    except Exception:
        return "-"

def _money(amount: Optional[float], ccy: Optional[str]) -> Optional[Dict[str, Any]]:
    if amount is None or ccy is None: return None
    return {"amount": round(float(amount), 2), "currency": ccy}

def _money_add(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not a and not b: return None
    if a and not b: return {"amount": round(float(a["amount"]), 2), "currency": a["currency"]}
    if b and not a: return {"amount": round(float(b["amount"]), 2), "currency": b["currency"]}
    if a["currency"] == b["currency"]:
        return {"amount": round(float(a["amount"]) + float(b["amount"]), 2), "currency": a["currency"]}
    # currency mismatch (MVP): keep 'a'
    return {"amount": round(float(a["amount"]), 2), "currency": a["currency"]}

def _sum_money_list(lst: List[Optional[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    out = None
    for m in lst:
        if m: out = _money_add(out, m)
    return out

def _prefer_target_money(entry: Optional[Dict[str, Any]], fallback: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Prefer a target-currency dict if present (e.g., price_target).
    If 'entry' is already a money dict, return it.
    Else if 'fallback' is a money dict, return that.
    """
    if entry and isinstance(entry, dict) and "amount" in entry and "currency" in entry:
        return {"amount": float(entry["amount"]), "currency": entry["currency"]}
    if fallback and isinstance(fallback, dict) and "amount" in fallback and "currency" in fallback:
        return {"amount": float(fallback["amount"]), "currency": fallback["currency"]}
    return None

def _meal_price_map(req: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Resolve meal prices we should use for per-day spend.
    Prefer orchestrator-stamped prices (trip.budget.meal_prices_used),
    else fallback to request.meal_prices, else defaults (Breakfast=8, Lunch=15, Dinner=25).
    """
    target_ccy = (
        (req.get("trip") or {}).get("budget", {}).get("target_currency")
        or req.get("target_currency")
        or ((req.get("fx") or {}).get("target"))
        or "EUR"
    )
    used = ((req.get("trip") or {}).get("budget") or {}).get("meal_prices_used")
    if not used:
        raw = (req.get("meal_prices") or {})
        used = {
            "MB": {"amount": float(raw.get("Breakfast", 8.0)), "currency": target_ccy},
            "ML": {"amount": float(raw.get("Lunch", 15.0)), "currency": target_ccy},
            "MD": {"amount": float(raw.get("Dinner", 25.0)), "currency": target_ccy},
        }
    else:
        # already in MB/ML/MD keyed form from orchestrator
        pass
    # Normalize keys to MB/ML/MD if someone passed Breakfast/Lunch/Dinner shape
    if "Breakfast" in used or "Lunch" in used or "Dinner" in used:
        used = {
            "MB": {"amount": float(used.get("Breakfast", 8.0)), "currency": target_ccy},
            "ML": {"amount": float(used.get("Lunch", 15.0)), "currency": target_ccy},
            "MD": {"amount": float(used.get("Dinner", 25.0)), "currency": target_ccy},
        }
    return used

def _city_cost_surfaces(req: Dict[str, Any], city: str):
    """Return (lodging_per_night, transit_per_day, poi_entry_map[name]->money) for city."""
    disc_city = ((req.get("discovery") or {}).get("cities") or {}).get(city) or {}
    costs = (disc_city.get("costs") or {})
    lodging_per_night = ((costs.get("lodging") or {}).get("per_night") or None)
    transit_per_day   = ((costs.get("transit") or {}).get("per_day_cost") or None)
    entry_map: Dict[str, Optional[Dict[str, Any]]] = {}
    for e in (costs.get("poi_entry") or []):
        nm = (e.get("name") or "").strip()
        if nm:
            # prefer target if available (e.g., {"entry_target": {...}, "entry": {...}})
            entry_target = _prefer_target_money(e.get("entry_target"), e.get("entry"))
            entry_map[nm] = entry_target
    return lodging_per_night, transit_per_day, entry_map

def _day_travel_cost(day: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    out = None
    for it in (day.get("items") or []):
        # Prefer pre-converted target cost if node provided it
        tc = _prefer_target_money(it.get("travel_cost_target"), it.get("travel_cost"))
        if tc and isinstance(tc.get("amount"), (int, float)):
            out = _money_add(out, tc)
    return out

def _day_meals_cost(day: Dict[str, Any], meal_prices: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    out = None
    for it in (day.get("items") or []):
        if it.get("type") == "meal":
            mid = it.get("node_id")
            p = meal_prices.get(mid)
            if p:
                out = _money_add(out, p)
    return out

def _day_poi_entry_cost(day: Dict[str, Any], entry_map: Dict[str, Optional[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    out = None
    for it in (day.get("items") or []):
        if it.get("type") == "poi":
            nm = (it.get("name") or "").strip()
            m = entry_map.get(nm)
            if m and isinstance(m.get("amount"), (int, float)):
                out = _money_add(out, m)
    return out

def _day_intercity_cost(day: Dict[str, Any], intercity_timeline: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Prefer hop.price_target over hop.price; both are money dicts."""
    dt = day.get("date")
    out = None
    for hop in (intercity_timeline or []):
        if hop.get("date") == dt:
            p = _prefer_target_money(hop.get("price_target"), hop.get("price"))
            if p and isinstance(p.get("amount"), (int, float)):
                out = _money_add(out, p)
    return out

# ---------- main ----------
def writer_report(state: AppState) -> AppState:
    """
    Consumes state.request['trip'] and emits:
      - request['report']['json']               (structured, includes per_day)
      - request['report']['markdown']           (overview with day-by-day items)
      - request['report']['markdown_daily']     (per-day spend summary)
    """
    req, logs = state.request, state.logs or []
    state.meta = state.meta or {}

    trip = req.get("trip") or {}
    if not trip:
        state.meta["requires_input"] = {"field": "trip", "message": "trip missing (run orchestrator first)"}
        state.logs = logs; return state

    days: List[Dict[str, Any]] = trip.get("days") or []
    totals = trip.get("totals") or {}
    budget = trip.get("budget") or {}
    nights_by_city = trip.get("nights_by_city") or {}
    cities = req.get("cities") or []
    intercity_tl = trip.get("intercity") or []

    target_ccy = (
        budget.get("target_currency")
        or req.get("target_currency")
        or ((req.get("fx") or {}).get("target"))
        or "EUR"
    )
    meal_prices = _meal_price_map(req)

    # Build concise day items for JSON and prepare per-day spend
    json_days = []
    per_day_report = []

    for d in days:
        city = d.get("city")
        lodging_per_night, transit_per_day, entry_map = _city_cost_surfaces(req, city)

        # Spend parts (already target currency if upstream normalized)
        lodging    = lodging_per_night
        transit    = transit_per_day
        travel     = _day_travel_cost(d)
        meals      = _day_meals_cost(d, meal_prices)
        poi_entry  = _day_poi_entry_cost(d, entry_map)
        intercity  = _day_intercity_cost(d, intercity_tl)

        day_total = _sum_money_list([lodging, transit, travel, meals, poi_entry, intercity])

        # Counts
        poi_count = d.get("totals", {}).get("poi_count", 0)
        meal_count = d.get("totals", {}).get("meal_count", 0)
        meal_breakdown = {"Breakfast": 0, "Lunch": 0, "Dinner": 0}
        for it in (d.get("items") or []):
            if it.get("type") == "meal":
                mid = it.get("node_id")
                if mid == "MB": meal_breakdown["Breakfast"] += 1
                elif mid == "ML": meal_breakdown["Lunch"] += 1
                elif mid == "MD": meal_breakdown["Dinner"] += 1

        # Items view for JSON (use target cost if provided)
        items = []
        for it in (d.get("items") or []):
            items.append({
                "type": it.get("type"),
                "name": it.get("name"),
                "from": it.get("from_id"),
                "mode": it.get("mode"),
                "travel_min": it.get("travel_min"),
                "included_in_pass": it.get("included_in_pass", False),
                "travel_cost": _prefer_target_money(it.get("travel_cost_target"), it.get("travel_cost")),
                "start": _hm(it.get("start_min")),
                "end": _hm(it.get("end_min")),
            })

        json_days.append({
            "date": d.get("date"),
            "city": city,
            "start": _hm(d.get("day_start_min")),
            "end": _hm(d.get("day_end_min")),
            "items": items,
            "totals": d.get("totals"),
        })

        per_day_report.append({
            "date": d.get("date"),
            "city": city,
            "counts": {"pois": poi_count, "meals": meal_count, "meals_breakdown": meal_breakdown},
            "spend": {
                "lodging": lodging,
                "transit": transit,
                "travel": travel,
                "meals": meals,
                "poi_entry": poi_entry,
                "intercity": intercity,
                "total": day_total,
            },
        })

    # High-level JSON report
    report_json = {
        "as_of": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "trip": {
            "cities": cities,
            "nights_by_city": nights_by_city,
            "budget": {**budget, "target_currency": target_ccy},
            "totals": totals,
            "intercity": intercity_tl,
            "per_day": per_day_report,
            "days": json_days,
        },
    }

    # Overview Markdown
    lines = []
    lines.append(f"# Trip Itinerary ({target_ccy})")
    lines.append("")
    lines.append(f"**Budget cap:** {budget.get('cap_total')} (include lodging: {budget.get('include_lodging', True)}) → **Met:** {budget.get('met')}")
    if budget.get("spend_total"):
        lines.append(f"**Budget spend considered:** {_money_str(budget['spend_total'])}")
    lines.append("")
    lines.append("## Totals")
    lines.append(f"- Lodging: {_money_str(totals.get('lodging'))}")
    lines.append(f"- Transit (passes): {_money_str(totals.get('transit'))}")
    lines.append(f"- Intercity: {_money_str(totals.get('intercity'))}")
    lines.append(f"- In-city travel: {_money_str(totals.get('travel'))}")
    lines.append(f"- POI entries: {_money_str(totals.get('poi_entry'))}")
    if totals.get("meals"): lines.append(f"- Meals: {_money_str(totals.get('meals'))}")
    lines.append(f"- **Grand total:** {_money_str(totals.get('grand_total'))}")
    lines.append("")
    lines.append("## Nights by city")
    for c in cities:
        lines.append(f"- {c}: {nights_by_city.get(c, 0)} nights")
    lines.append("")
    lines.append("## Day-by-day")
    for d in json_days:
        lines.append(f"### {d['date']} – {d.get('city','')}")
        lines.append(f"_Window: {d['start']}–{d['end']}_")
        if not d["items"]:
            lines.append("- (no scheduled items)")
        else:
            for it in d["items"]:
                tt = f"{it['start']}-{it['end']}"
                kind = it['type']
                name = it['name']
                mode = it.get('mode') or "-"
                travel = f"{(it.get('travel_min') or 0)} min"
                if it.get("included_in_pass"):
                    cost_txt = "included in pass"
                else:
                    cost_txt = _money_str(it.get("travel_cost"))
                lines.append(f"- **{tt}** · *{kind}* · {name} — via **{mode}** ({travel}, {cost_txt})")
        lines.append("")

    report_md = "\n".join(lines)

    # Per-day Spend Markdown
    dm = []
    dm.append("# Per-day Spend Summary")
    for pd in per_day_report:
        dm.append(f"## {pd['date']} – {pd['city']}")
        dm.append(f"- Lodging:    {_money_str(pd['spend'].get('lodging'))}")
        dm.append(f"- Transit:    {_money_str(pd['spend'].get('transit'))}")
        dm.append(f"- In-city:    {_money_str(pd['spend'].get('travel'))}")
        dm.append(f"- POI entry:  {_money_str(pd['spend'].get('poi_entry'))}")
        dm.append(f"- Meals:      {_money_str(pd['spend'].get('meals'))}")
        dm.append(f"- Intercity:  {_money_str(pd['spend'].get('intercity'))}")
        dm.append(f"- **Total:**  {_money_str(pd['spend'].get('total'))}")
        mb = pd.get("counts", {}).get("meals_breakdown", {})
        dm.append(f"  - Meals taken: B={mb.get('Breakfast',0)}  L={mb.get('Lunch',0)}  D={mb.get('Dinner',0)}")
        dm.append("")
    report_md_daily = "\n".join(dm)

    req["report"] = {"json": report_json, "markdown": report_md, "markdown_daily": report_md_daily}
    logs.append("Writer_Report: emitted report.json + report.markdown + per-day summary")
    state.request, state.logs = req, logs
    return state
