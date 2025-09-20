# # app/graph/travel_graph.py
# from __future__ import annotations
# import os, warnings, traceback
# from typing import Any, Dict, List, Optional, Tuple
# from typing_extensions import TypedDict
# from langgraph.graph import StateGraph, END

# # === Gap node (real) ===
# from app.graph.nodes_new.critic_data import node_gap_search_fill  # we’ll wrap it

# # Toggle: if true, tool nodes return local mock data (no Tavily/OpenAI calls)
# USE_MOCK = os.getenv("TP_MOCK_TOOLS", "").lower() in ("1", "true", "yes")
# ENABLE_PD_TRACE = os.getenv("PD_TRACE", "0") == "1"

# # NEW: limit how many missing items the critic fills in one pass (default 2)
# GAP_MAX_ITEMS = int(os.getenv("TP_GAP_MAX_ITEMS", "2") or "2")

# # ===== Debug / Dump helpers =====
# import json, pathlib

# def _to_json(obj: Any, clip: int | None = None) -> str:
#     def _default(o):
#         if hasattr(o, "model_dump"):
#             return o.model_dump()
#         if hasattr(o, "__dict__"):
#             return o.__dict__
#         return str(o)
#     s = json.dumps(obj, indent=2, ensure_ascii=False, default=_default)
#     if clip and len(s) > clip:
#         return s[:clip] + "\n…[clipped]"
#     return s

# def dump_state_files(state: "TravelState", out_dir: str = "debug") -> None:
#     d = pathlib.Path(out_dir)
#     d.mkdir(parents=True, exist_ok=True)
#     (d / "state.json").write_text(_to_json(state), encoding="utf-8")
#     (d / "interp.json").write_text(_to_json(state.get("interp", {})), encoding="utf-8")
#     (d / "fx.json").write_text(_to_json(state.get("fx", {})), encoding="utf-8")
#     (d / "poi.json").write_text(_to_json(state.get("poi", {})), encoding="utf-8")
#     (d / "restaurants.json").write_text(_to_json(state.get("restaurants", {})), encoding="utf-8")
#     (d / "city_fares.json").write_text(_to_json(state.get("city_fares", {})), encoding="utf-8")
#     (d / "intercity.json").write_text(_to_json(state.get("intercity", {})), encoding="utf-8")
#     (d / "logs.txt").write_text("\n".join(state.get("logs", [])), encoding="utf-8")

# def print_state_summary(state: "TravelState", per_city_sample: int = 5) -> None:
#     print("\n=== INTERP ===")
#     print(_to_json(state.get("interp", {})))

#     print("\n=== FX ===")
#     fx_meta = state.get("fx_meta", {})
#     print(f"target={fx_meta.get('target')} | rates={len((fx_meta.get('to_target') or {}))}")

#     poi = state.get("poi") or {}
#     pbc = (poi.get("poi_by_city") or {})
#     print("\n=== POI (by city) ===")
#     for city, payload in pbc.items():
#         names = [p.get("name") for p in (payload.get("pois") or []) if p.get("name")]
#         print(f"  - {city}: {len(names)} POIs", f"| sample: {names[:per_city_sample]}" if names else "")

#     rest = state.get("restaurants") or {}
#     names_by_city = rest.get("names_by_city") or {}
#     links_by_city = rest.get("links_by_city") or {}
#     print("\n=== RESTAURANTS ===")
#     for city in sorted(set(names_by_city) | set(links_by_city)):
#         n = len(names_by_city.get(city, []) or [])
#         l = len(links_by_city.get(city, []) or [])
#         sample = (names_by_city.get(city, []) or [])[:per_city_sample]
#         print(f"  - {city}: names={n}, links={l}", f"| sample: {sample}" if sample else "")

#     cf = (state.get("city_fares") or {}).get("city_fares") or {}
#     print("\n=== CITY FARES ===")
#     for city, payload in cf.items():
#         tr = (payload.get("transit") or {})
#         tx = (payload.get("taxi") or {})
#         def _m(m):
#             return None if not m else f"{m.get('amount')} {m.get('currency')}"
#         print(f"  - {city}: "
#               f"transit(single={_m(tr.get('single'))}, day={_m(tr.get('day_pass'))}, weekly={_m(tr.get('weekly_pass'))}); "
#               f"taxi(base={tx.get('base')} {tx.get('currency')}, per_km={tx.get('per_km')}, per_min={tx.get('per_min')})")

#     ic = state.get("intercity") or {}
#     hops = ic.get("hops") or []
#     print("\n=== INTERCITY ===")
#     print(f"hops={len(hops)}")
#     for h in hops[:per_city_sample]:
#         print(f"  - {h.get('from')} → {h.get('to')} | mode={h.get('mode')} | "
#               f"duration={h.get('duration')} | price={h.get('price')} {h.get('currency')}")

#     print("\n=== LOGS (last 20) ===")
#     for ln in state.get("logs", [])[-20:]:
#         print("  " + ln)

# def _trace_model(model: Any, label: str, state: "TravelState") -> None:
#     if not ENABLE_PD_TRACE or model is None:
#         return
#     try:
#         with warnings.catch_warnings(record=True) as rec:
#             warnings.simplefilter("always")
#             model.model_dump()
#             for w in rec:
#                 msg = str(w.message)
#                 if "PydanticSerialization" in msg or "serializer warnings" in msg:
#                     state.setdefault("logs", []).append(f"[PD-WARN] {label}: {msg}")
#                     stack = "".join(traceback.format_stack(limit=6)).splitlines()
#                     for line in stack[-5:]:
#                         state["logs"].append("    " + line)
#     except Exception as e:
#         state.setdefault("logs", []).append(f"[PD-TRACE-ERR] {label}: {e!r}")

# # --- Interpreter ---
# from app.graph.nodes_new.interpreter import interpret

# # --- Real tool APIs (used when not mocking) ---
# from app.graph.nodes.city_recommender_tool import (
#     city_recommender_tool, CityRecommenderArgs, CountryArg as RecCountryArg
# )
# from app.graph.nodes.currency_tool import (
#     fx_oracle_tool, FxOracleArgs, CountryArg as FxCountryArg
# )
# from app.graph.nodes.POI_discovery_tool import (
#     poi_discovery_tool, POIDiscoveryArgs
# )
# from app.graph.nodes.restaurants_discovery_tool import (
#     restaurants_discovery_tool, RestaurantsDiscoveryArgs
# )
# from app.graph.nodes.city_fare_tool import (
#     cityfares_discovery_tool, CityFaresArgs
# )
# from app.graph.nodes.intercity_fare_tool import (
#     intercity_discovery_tool, IntercityDiscoveryArgs
# )

# # ---------------- State ----------------
# class TravelState(TypedDict, total=False):
#     user_message: str
#     interp: Dict[str, Any]
#     plan_queue: List[str]
#     done_tools: List[str]
#     last_tool: Optional[str]
#     logs: List[str]
#     errors: List[str]
#     countries: List[Dict[str, Any]]
#     cities: List[str]
#     city_country_map: Dict[str, str]
#     fx: Dict[str, Any]
#     fx_meta: Dict[str, Any]
#     poi: Dict[str, Any]
#     restaurants: Dict[str, Any]
#     city_fares: Dict[str, Any]
#     intercity: Dict[str, Any]
#     # NEW: let the critic read this to cap how many specs to fill in one pass
#     gap_max_items: Optional[int]

# KNOWN = {"cities.recommender","fx.oracle","poi.discovery","restaurants.discovery","fares.city","fares.intercity"}
# STOP_WORDS = {"writer.report"}
# SKIP_WORDS = {"discovery.costs", "graph.city", "opt.greedy", "trip.maker"}

# def _init_lists(state: TravelState) -> None:
#     state.setdefault("logs", [])
#     state.setdefault("errors", [])
#     state.setdefault("plan_queue", [])
#     state.setdefault("done_tools", [])

# def _flatten_cities(interp: Dict[str, Any]) -> List[str]:
#     out: List[str] = []
#     for ci in (interp.get("countries") or []):
#         for nm in (ci.get("cities") or []):
#             s = (nm or "").strip()
#             if s:
#                 out.append(s)
#     seen, res = set(), []
#     for c in out:
#         if c not in seen:
#             seen.add(c); res.append(c)
#     return res

# def _mk_city_country_map(interp: Dict[str, Any]) -> Dict[str, str]:
#     m: Dict[str, str] = {}
#     for ci in (interp.get("countries") or []):
#         country = (ci.get("country") or "").strip() or (ci.get("name") or "").strip()
#         for nm in (ci.get("cities") or []):
#             city = (nm or "").strip()
#             if city:
#                 m[city] = country
#     return m

# # ---------------- Goal checks ----------------
# def _has_cities(state: TravelState) -> bool:
#     return bool(state.get("cities"))

# def _has_poi(state: TravelState) -> bool:
#     poi = state.get("poi") or {}
#     by_city = poi.get("poi_by_city") or {}
#     return any((v.get("pois") if isinstance(v, dict) else None) for v in by_city.values())

# def _has_restaurants(state: TravelState) -> bool:
#     rest = state.get("restaurants") or {}
#     return bool((rest.get("links_by_city") or {}) or (rest.get("names_by_city") or {}))

# def _has_city_fares(state: TravelState) -> bool:
#     cf = state.get("city_fares") or {}
#     return bool(cf.get("city_fares"))

# def _has_intercity(state: TravelState) -> bool:
#     ic = state.get("intercity") or {}
#     return bool(ic.get("hops"))

# def _need_fx(state: TravelState) -> bool:
#     interp = state.get("interp") or {}
#     tgt = (interp.get("target_currency") or "EUR").upper()
#     needs = (tgt != "EUR") or bool(interp.get("budget_caps"))
#     already = bool(state.get("fx"))
#     has_countries = bool(interp.get("countries"))
#     return needs and (not already) and has_countries

# def _goal_satisfied(state: TravelState) -> bool:
#     intent = (state.get("interp") or {}).get("intent")
#     if intent == "recommend_cities":
#         return _has_cities(state)
#     if intent == "poi_lookup":
#         return _has_cities(state) and _has_poi(state)
#     if intent == "restaurants_nearby":
#         return _has_cities(state) and _has_restaurants(state)
#     if intent == "city_fares":
#         return _has_cities(state) and _has_city_fares(state)
#     if intent == "intercity_fares":
#         return len(state.get("cities") or []) >= 2 and _has_intercity(state)
#     if intent == "plan_trip":
#         has_c = _has_cities(state)
#         has_p = _has_poi(state) or _has_restaurants(state)
#         return has_c and has_p and _has_city_fares(state) and _has_intercity(state)
#     return True

# # ---------------- Planning ----------------
# def _compute_next_plan(state: TravelState) -> List[str]:
#     interp = state.get("interp") or {}
#     done = set(state.get("done_tools") or [])
#     plan = [t for t in (interp.get("tool_plan") or []) if t in KNOWN]

#     if not _has_cities(state) and (interp.get("countries") or []):
#         if "cities.recommender" not in plan and "cities.recommender" not in done:
#             plan = ["cities.recommender"] + plan

#     if _need_fx(state) and "fx.oracle" not in plan and "fx.oracle" not in done:
#         inserted = False
#         for i, t in enumerate(plan):
#             if t in ("fares.city", "fares.intercity"):
#                 plan.insert(i, "fx.oracle")
#                 inserted = True
#                 break
#         if not inserted:
#             plan.append("fx.oracle")

#     def add_once(t: str):
#         if t not in plan and t not in done:
#             plan.append(t)

#     intent = interp.get("intent")
#     if intent in ("city_fares",):
#         add_once("fares.city")
#     elif intent in ("intercity_fares",):
#         add_once("fares.intercity")
#     elif intent in ("poi_lookup",):
#         add_once("poi.discovery")
#     elif intent in ("restaurants_nearby",):
#         add_once("restaurants.discovery")
#     elif intent == "plan_trip":
#         for t in ("fares.city", "fares.intercity", "poi.discovery", "restaurants.discovery"):
#             add_once(t)

#     def needed(t: str) -> bool:
#         if t == "cities.recommender": return not _has_cities(state)
#         if t == "fx.oracle":          return _need_fx(state)
#         if t == "fares.city":         return not _has_city_fares(state) and _has_cities(state)
#         if t == "fares.intercity":    return not _has_intercity(state) and len(state.get("cities") or []) >= 2
#         if t == "poi.discovery":      return not _has_poi(state) and _has_cities(state)
#         if t == "restaurants.discovery": return not _has_restaurants(state) and _has_cities(state)
#         return True

#     plan = [t for t in plan if (t not in done) and needed(t)]
#     return plan

# # ---------------- Nodes ----------------
# def node_interpret(state: TravelState) -> TravelState:
#     _init_lists(state)
#     msg = state.get("user_message") or ""
#     inter = interpret(msg)
#     _trace_model(inter, "Interpretation", state)

#     data = inter.model_dump()
#     state["interp"] = data
#     state["countries"] = data.get("countries") or []
#     state["cities"] = _flatten_cities(data)
#     state["city_country_map"] = _mk_city_country_map(data)
#     state["plan_queue"] = _compute_next_plan(state)
#     state["logs"].append(f"[interpret] intent={data.get('intent')} plan={state['plan_queue']}")
#     return state

# def node_replan(state: TravelState) -> TravelState:
#     state["plan_queue"] = _compute_next_plan(state)
#     state["logs"].append(f"[replan] next={state['plan_queue']}")
#     return state

# def router(state: TravelState) -> str:
#     q = state.get("plan_queue") or []
#     if q:
#         nxt = q.pop(0)
#         state["plan_queue"] = q
#         state["last_tool"] = nxt
#         state.setdefault("logs", []).append(f"[route] → {nxt}")
#         return nxt

#     if _goal_satisfied(state):
#         state.setdefault("logs", []).append("[router] goal satisfied → END")
#         return END

#     new_plan = _compute_next_plan(state)
#     if new_plan:
#         nxt = new_plan.pop(0)
#         state["plan_queue"] = new_plan
#         state["last_tool"] = nxt
#         state.setdefault("logs", []).append(f"[router] recomputed → {nxt}")
#         return nxt

#     state.setdefault("logs", []).append("[router] no plan and goal not satisfied → END")
#     return END

# # ---------- MOCK UTILITIES ----------
# _CCY_BY_COUNTRY = {
#     "Japan": "JPY", "United States": "USD", "United Kingdom": "GBP", "France": "EUR",
#     "Italy": "EUR", "Spain": "EUR", "Germany": "EUR", "Canada": "CAD", "Australia": "AUD",
# }
# _DEF_POIS = ["City Museum", "Botanical Garden", "Central Park", "Old Town Gate"]
# _DEF_RESTS = ["Local Bistro", "Noodle House", "Steak Corner", "Seafood Shack"]

# # --- Tool nodes (each fully wrapped; never raise) ---
# def node_cities_recommender(state: TravelState) -> TravelState:
#     try:
#         if USE_MOCK:
#             interp = state.get("interp") or {}
#             cities = state.get("cities") or ["Tokyo", "Kyoto"]
#             ctry = state.get("city_country_map") or _mk_city_country_map(interp) or {"Tokyo": "Japan", "Kyoto": "Japan"}
#             state["cities"] = cities
#             state["city_country_map"] = ctry
#             state["logs"].append(f"[cities.recommender][mock] picked={cities}")
#         else:
#             interp = state.get("interp") or {}
#             rec_countries = []
#             for c in (interp.get("countries") or []):
#                 nm = (c.get("country") or c.get("name") or "").strip()
#                 if nm:
#                     rec_countries.append(RecCountryArg(country=nm, cities=(c.get("cities") or [])))
#             if not rec_countries:
#                 state["logs"].append("[cities.recommender] skipped: no countries")
#             else:
#                 args = CityRecommenderArgs(
#                     countries=rec_countries,
#                     dates=(interp.get("dates") or None) if (interp.get("dates") or {}).get("start") else None,
#                     travelers=interp.get("travelers") or {"adults":1,"children":0},
#                     musts=interp.get("musts") or [],
#                     preferred_cities=(interp.get("preferences") or {}).get("preferred_cities") or [],
#                     preferences=interp.get("preferences") or {},
#                 )
#                 _trace_model(args, "CityRecommenderArgs", state)
#                 res = city_recommender_tool(args)
#                 _trace_model(res, "CityRecommenderResult", state)
#                 state["cities"] = list(res.cities or [])
#                 state["city_country_map"] = dict(res.city_country_map or {})
#                 state["logs"].append(f"[cities.recommender] picked={state.get('cities')}")
#     except Exception as e:
#         state["errors"].append(f"cities.recommender: {e}")
#         state["logs"].append(f"[cities.recommender] ERROR: {e}")
#     finally:
#         state.setdefault("done_tools", []).append("cities.recommender")
#     return state

# def node_fx_oracle(state: TravelState) -> TravelState:
#     try:
#         if USE_MOCK:
#             ctry_map = state.get("city_country_map") or {}
#             currency_by_country: Dict[str, str] = {}
#             for c in set(ctry_map.values()):
#                 if c:
#                     currency_by_country[c] = _CCY_BY_COUNTRY.get(c, "USD")
#             target = ((state.get("interp") or {}).get("target_currency") or "USD").upper()
#             state["fx"] = {"target": target, "to_target": {}, "currency_by_country": currency_by_country}
#             state["fx_meta"] = {"target": target, "to_target": {}, "currency_by_country": currency_by_country}
#             state["logs"].append("[fx.oracle][mock] ok")
#         else:
#             interp = state.get("interp") or {}
#             countries = []
#             for ci in (interp.get("countries") or []):
#                 nm = (ci.get("country") or ci.get("name") or "").strip()
#                 if nm:
#                     countries.append(FxCountryArg(country=nm))
#             if not countries:
#                 state["logs"].append("[fx.oracle] skipped: no countries")
#             else:
#                 fx_args = FxOracleArgs(
#                     countries=countries,
#                     city_country_map=state.get("city_country_map") or {},
#                     target_currency=(interp.get("target_currency") or None),
#                     preferences=interp.get("preferences") or {},
#                 )
#                 _trace_model(fx_args, "FxOracleArgs", state)
#                 fx_res = fx_oracle_tool(fx_args)
#                 _trace_model(fx_res, "FxOracleResult", state)
#                 state["fx"] = fx_res.model_dump()
#                 state["fx_meta"] = {
#                     "currency_by_country": fx_res.currency_by_country,
#                     "target": fx_res.target,
#                     "to_target": fx_res.to_target,
#                 }
#                 state["logs"].append("[fx.oracle] ok")
#     except Exception as e:
#         state["errors"].append(f"fx.oracle: {e}")
#         state["logs"].append(f"[fx.oracle] ERROR: {e}")
#     finally:
#         state.setdefault("done_tools", []).append("fx.oracle")
#     return state

# def node_city_fares(state: TravelState) -> TravelState:
#     try:
#         if USE_MOCK:
#             cities = state.get("cities") or []
#             ctry = state.get("city_country_map") or {}
#             payload: Dict[str, Any] = {"city_fares": {}}
#             for c in cities:
#                 cc = ctry.get(c)
#                 payload["city_fares"][c] = {
#                     "transit": {
#                         "single": None,
#                         "day_pass": None,
#                         "weekly_pass": None,
#                     },
#                     "taxi": {
#                         "base": None, "per_km": None, "per_min": None,
#                         "currency": _CCY_BY_COUNTRY.get(cc),
#                     },
#                 }
#             state["city_fares"] = payload
#             state["logs"].append(f"[fares.city][mock] ok ({len(cities)} cities)")
#         else:
#             cities = state.get("cities") or []
#             if not cities:
#                 state["logs"].append("[fares.city] skipped: no cities")
#             else:
#                 args = CityFaresArgs(
#                     cities=cities,
#                     city_country_map=state.get("city_country_map") or {},
#                     preferences=(state.get("interp") or {}).get("preferences") or {},
#                     travelers=(state.get("interp") or {}).get("travelers"),
#                     musts=(state.get("interp") or {}).get("musts") or [],
#                     fx_target=(state.get("fx") or {}).get("target"),
#                     fx_to_target=(state.get("fx") or {}).get("to_target"),
#                 )
#                 _trace_model(args, "CityFaresArgs", state)
#                 res = cityfares_discovery_tool(args)
#                 _trace_model(res, "CityFaresResult", state)
#                 state["city_fares"] = res.model_dump()
#                 state["logs"].append(f"[fares.city] ok ({len(cities)} cities)")
#     except Exception as e:
#         state["errors"].append(f"fares.city: {e}")
#         state["logs"].append(f"[fares.city] ERROR: {e}")
#     finally:
#         state.setdefault("done_tools", []).append("fares.city")
#     return state

# def node_intercity(state: TravelState) -> TravelState:
#     try:
#         if USE_MOCK:
#             cities = state.get("cities") or []
#             hops_list: List[Dict[str, Any]] = []
#             for i in range(len(cities)-1):
#                 a, b = cities[i], cities[i+1]
#                 hops_list.append({"from": a, "to": b, "mode": None, "duration": None, "price": None, "currency": None})
#             state["intercity"] = {"hops": hops_list}
#             state["logs"].append(f"[fares.intercity][mock] ok ({max(0,len(cities)-1)} hops)")
#         else:
#             cities = state.get("cities") or []
#             if len(cities) < 2:
#                 state["logs"].append("[fares.intercity] skipped: need >=2 cities")
#             else:
#                 args = IntercityDiscoveryArgs(
#                     cities=cities,
#                     city_country_map=state.get("city_country_map") or {},
#                     fx=(state.get("fx") or None),
#                     fx_target=(state.get("fx") or {}).get("target"),
#                     fx_to_target=(state.get("fx") or {}).get("to_target"),
#                     preferences=(state.get("interp") or {}).get("preferences") or {},
#                     travelers=(state.get("interp") or {}).get("travelers"),
#                     musts=(state.get("interp") or {}).get("musts") or [],
#                 )
#                 _trace_model(args, "IntercityDiscoveryArgs", state)
#                 res = intercity_discovery_tool(args)
#                 _trace_model(res, "IntercityDiscoveryResult", state)
#                 state["intercity"] = res.model_dump()
#                 state["logs"].append(f"[fares.intercity] ok ({len(cities)-1} hops)")
#     except Exception as e:
#         state["errors"].append(f"fares.intercity: {e}")
#         state["logs"].append(f"[fares.intercity] ERROR: {e}")
#     finally:
#         state.setdefault("done_tools", []).append("fares.intercity")
#     return state

# def node_poi(state: TravelState) -> TravelState:
#     try:
#         if USE_MOCK:
#             cities = state.get("cities") or []
#             by_city: Dict[str, Any] = {}
#             for c in cities:
#                 by_city[c] = {"pois": [{"name": n} for n in _DEF_POIS]}
#             state["poi"] = {"poi_by_city": by_city}
#             state["logs"].append(f"[poi.discovery][mock] ok ({len(cities)} cities)")
#         else:
#             cities = state.get("cities") or []
#             if not cities:
#                 state["logs"].append("[poi.discovery] skipped: no cities")
#             else:
#                 args = POIDiscoveryArgs(
#                     cities=cities,
#                     city_country_map=state.get("city_country_map") or {},
#                     travelers=(state.get("interp") or {}).get("travelers") or {"adults":1,"children":0},
#                     musts=(state.get("interp") or {}).get("musts") or [],
#                     preferences=(state.get("interp") or {}).get("preferences") or {},
#                 )
#                 _trace_model(args, "POIDiscoveryArgs", state)
#                 res = poi_discovery_tool(args)
#                 _trace_model(res, "POIDiscoveryResult", state)
#                 state["poi"] = res.model_dump()
#                 state["logs"].append(f"[poi.discovery] ok ({len(cities)} cities)")
#     except Exception as e:
#         state["errors"].append(f"poi.discovery: {e}")
#         state["logs"].append(f"[poi.discovery] ERROR: {e}")
#     finally:
#         state.setdefault("done_tools", []).append("poi.discovery")
#     return state

# def node_restaurants(state: TravelState) -> TravelState:
#     try:
#         if USE_MOCK:
#             cities = state.get("cities") or []
#             names_by_city: Dict[str, Any] = {}
#             for c in cities:
#                 names_by_city[c] = {"core": [{"name": n} for n in _DEF_RESTS]}
#             state["restaurants"] = {
#                 "names_by_city": names_by_city,
#                 "links_by_city": {},
#                 "details_by_city": {},
#             }
#             state["logs"].append(f"[restaurants.discovery][mock] ok ({len(cities)} cities)")
#         else:
#             cities = state.get("cities") or []
#             if not cities:
#                 state["logs"].append("[restaurants.discovery] skipped: no cities")
#             else:
#                 pois_by_city = {}
#                 poi_blob = (state.get("poi") or {}).get("poi_by_city") or {}
#                 if isinstance(poi_blob, dict):
#                     for city, payload in poi_blob.items():
#                         names = []
#                         for p in (payload.get("pois") or []):
#                             nm = (p.get("name") or "").strip()
#                             if nm:
#                                 names.append(nm)
#                         if names:
#                             pois_by_city[city] = names[:8]
#                 args = RestaurantsDiscoveryArgs(
#                     cities=cities,
#                     pois_by_city=(pois_by_city or None),
#                     travelers=(state.get("interp") or {}).get("travelers"),
#                     musts=(state.get("interp") or {}).get("musts") or [],
#                     preferences=(state.get("interp") or {}).get("preferences") or {},
#                 )
#                 _trace_model(args, "RestaurantsDiscoveryArgs", state)
#                 res = restaurants_discovery_tool(args)
#                 _trace_model(res, "RestaurantsDiscoveryResult", state)
#                 state["restaurants"] = res.model_dump()
#                 state["logs"].append(f"[restaurants.discovery] ok ({len(cities)} cities)")
#     except Exception as e:
#         state["errors"].append(f"restaurants.discovery: {e}")
#         state["logs"].append(f"[restaurants.discovery] ERROR: {e}")
#     finally:
#         state.setdefault("done_tools", []).append("restaurants.discovery")
#     return state

# # --------- GAP WRAPPER (cap to N items & run once) ----------
# def node_gap_search_fill_limited(state: TravelState) -> TravelState:
#     """
#     Inject a limit so the critic only fills up to GAP_MAX_ITEMS specs in this pass.
#     Then delegate to the real gap node.
#     """
#     try:
#         state["gap_max_items"] = GAP_MAX_ITEMS
#     except Exception:
#         pass
#     # Run the real critic once
#     try:
#         out = node_gap_search_fill(state)
#         # Mark that we ran the limited gap once (optional log)
#         (out.setdefault("logs", [])).append(f"[gap.search_fill][cap={GAP_MAX_ITEMS}] ran once")
#         return out
#     except Exception as e:
#         state.setdefault("errors", []).append(f"gap.search_fill: {e}")
#         state.setdefault("logs", []).append(f"[gap.search_fill] ERROR: {e}")
#         return state

# def build_graph() -> StateGraph:
#     g = StateGraph(TravelState)

#     # regular nodes
#     g.add_node("interpret", node_interpret)
#     g.add_node("replan", node_replan)

#     # tool nodes
#     g.add_node("cities.recommender", node_cities_recommender)
#     g.add_node("fx.oracle", node_fx_oracle)
#     g.add_node("fares.city", node_city_fares)
#     g.add_node("fares.intercity", node_intercity)
#     g.add_node("poi.discovery", node_poi)
#     g.add_node("restaurants.discovery", node_restaurants)

#     # gap node (limited, one pass)
#     g.add_node("gap.search_fill", node_gap_search_fill_limited)

#     # ENTRY
#     g.set_entry_point("interpret")

#     # interpret → router → (tools | gap.search_fill)
#     g.add_conditional_edges(
#         "interpret",
#         router,
#         {
#             "cities.recommender": "cities.recommender",
#             "fx.oracle": "fx.oracle",
#             "fares.city": "fares.city",
#             "fares.intercity": "fares.intercity",
#             "poi.discovery": "poi.discovery",
#             "restaurants.discovery": "restaurants.discovery",
#             # END now goes to the gap node once
#             END: "gap.search_fill",
#         },
#     )

#     # each tool loops back to replan
#     for tool in [
#         "cities.recommender",
#         "fx.oracle",
#         "fares.city",
#         "fares.intercity",
#         "poi.discovery",
#         "restaurants.discovery",
#     ]:
#         g.add_edge(tool, "replan")

#     # replan → router → (tools | gap.search_fill)
#     g.add_conditional_edges(
#         "replan",
#         router,
#         {
#             "cities.recommender": "cities.recommender",
#             "fx.oracle": "fx.oracle",
#             "fares.city": "fares.city",
#             "fares.intercity": "fares.intercity",
#             "poi.discovery": "poi.discovery",
#             "restaurants.discovery": "restaurants.discovery",
#             # send to the gap node once
#             END: "gap.search_fill",
#         },
#     )

#     # After a single gap pass → END (no loop)
#     g.add_edge("gap.search_fill", END)

#     return g

# # --------------- Run / Trace helpers ---------------
# def run_once(message: str) -> TravelState:
#     graph = build_graph().compile()
#     init: TravelState = {"user_message": message}
#     return graph.invoke(init)

# def trace_route(message: str) -> Tuple[List[str], TravelState]:
#     graph = build_graph().compile()
#     init: TravelState = {"user_message": message}
#     route: List[str] = []
#     for step in graph.stream(init, stream_mode="updates"):
#         for node_name in step.keys():
#             if isinstance(node_name, str) and node_name not in ("__start__", "__end__"):
#                 route.append(node_name)
#     final_state = graph.invoke(init)
#     return route, final_state

# if __name__ == "__main__":
#     # Tip: run with TP_MOCK_TOOLS=1 so everything is local,
#     # and TP_GAP_MAX_ITEMS=2 to ensure the critic fills at most two specs.
#     # Example:
#     #   TP_MOCK_TOOLS=1 TP_GAP_MAX_ITEMS=2 python -m app.graph.travel_graph
#     demo = "We’re two adults visiting Japan in April for ~9 days. We love food and museums. Show prices in USD. Please suggest cities, then POIs and restaurants."
#     state = run_once(demo)
#     print_state_summary(state, per_city_sample=5)



from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

# -------- Toggle: mock the first-phase data tools --------
USE_MOCK = True  # keep True for this test

# ====== Final tool imports (real) ======
from app.graph.nodes.discoveries_costs_tool import discovery_and_cost
from app.graph.nodes.city_graph_tool import geocost_assembler
from app.graph.nodes.optimizer_helper_tool import itinerary_optimizer_greedy
from app.graph.nodes.trip_maker_tool import trip_orchestrator

# ====== Gap node (real, optional) ======
try:
    from app.graph.nodes_new.critic_data import node_gap_search_fill, cond_gap_more_or_done
    HAVE_GAP = True
except Exception:
    HAVE_GAP = False
    node_gap_search_fill = None
    cond_gap_more_or_done = None

# ---------------- State ----------------
class TravelState(TypedDict, total=False):
    # input
    user_message: str

    # execution bookkeeping
    plan_queue: List[str]
    done_tools: List[str]
    last_tool: Optional[str]
    logs: List[str]
    errors: List[str]

    # phase-1 artifacts (mocked)
    countries: List[Dict[str, Any]]
    cities: List[str]
    city_country_map: Dict[str, str]
    fx: Dict[str, Any]
    fx_meta: Dict[str, Any]
    poi: Dict[str, Any]
    restaurants: Dict[str, Any]
    city_fares: Dict[str, Any]
    intercity: Dict[str, Any]

    # phase-2 (final) artifacts
    discovery: Dict[str, Any]
    geocost: Dict[str, Any]
    itinerary: Dict[str, Any]
    trip: Dict[str, Any]

    # final pipeline queue
    final_queue: List[str]
    final_done: List[str]

# ---------------- Utilities ----------------
def _init_lists(state: TravelState) -> None:
    state.setdefault("logs", [])
    state.setdefault("errors", [])
    state.setdefault("done_tools", [])
    state.setdefault("final_done", [])

# ---------------- MOCKED FIRST-PHASE DATA ----------------
_CCY_BY_COUNTRY = {
    "Japan": "JPY", "United States": "USD", "United Kingdom": "GBP",
    "France": "EUR", "Italy": "EUR", "Spain": "EUR", "Germany": "EUR",
    "Canada": "CAD", "Australia": "AUD",
}

def _seed_informative_data(state: TravelState) -> None:
    # cities
    cities = ["Tokyo", "Kyoto"]
    state["cities"] = cities
    state["city_country_map"] = {"Tokyo": "Japan", "Kyoto": "Japan"}
    state["countries"] = [{"country": "Japan", "cities": cities}]

    # FX (target USD)
    state["fx"] = {
        "target": "USD",
        "to_target": {"JPY": 0.0065},
        "currency_by_country": {"Japan": "JPY"},
    }
    state["fx_meta"] = state["fx"]

    # POI
    state["poi"] = {
        "poi_by_city": {
            "Tokyo": {
                "pois": [
                    {
                        "city": "Tokyo",
                        "name": "Tokyo National Museum",
                        "category": "museum",
                        "official_url": "https://www.tnm.jp/",
                        "hours": {"Mon": None, "Tue": "09:30–17:00", "Wed": "09:30–17:00", "Thu": "09:30–17:00", "Fri": "09:30–21:00", "Sat": "09:30–21:00", "Sun": "09:30–17:00"},
                        "price": {"adult": 1000.0, "child": 0.0, "currency": "JPY"},
                        "coords": {"lat": 35.7188, "lon": 139.7765},
                        "source_urls": ["https://www.tnm.jp/?lang=en"],
                    },
                    {
                        "city": "Tokyo",
                        "name": "Ueno Park",
                        "category": "park",
                        "official_url": "https://www.gotokyo.org/en/spot/19/index.html",
                        "hours": {"Mon": "Open", "Tue": "Open", "Wed": "Open", "Thu": "Open", "Fri": "Open", "Sat": "Open", "Sun": "Open"},
                        "price": {"adult": 0.0, "child": 0.0, "currency": "JPY"},
                        "coords": {"lat": 35.7148, "lon": 139.7745},
                        "source_urls": ["https://www.gotokyo.org/en/spot/19/index.html"],
                    },
                ],
                "sources": ["mock://tokyo-poi"]
            },
            "Kyoto": {
                "pois": [
                    {
                        "city": "Kyoto",
                        "name": "Fushimi Inari Shrine",
                        "category": "shrine",
                        "official_url": "https://inari.jp/en/",
                        "hours": {"Mon": "Open 24h","Tue": "Open 24h","Wed": "Open 24h","Thu": "Open 24h","Fri": "Open 24h","Sat": "Open 24h","Sun": "Open 24h"},
                        "price": {"adult": 0.0, "child": 0.0, "currency": "JPY"},
                        "coords": {"lat": 34.9671, "lon": 135.7727},
                        "source_urls": ["https://inari.jp/en/"],
                    },
                    {
                        "city": "Kyoto",
                        "name": "Kiyomizu-dera",
                        "category": "temple",
                        "official_url": "https://www.kiyomizudera.or.jp/en/",
                        "hours": {"Mon": "06:00–18:00","Tue": "06:00–18:00","Wed": "06:00–18:00","Thu": "06:00–18:00","Fri": "06:00–18:00","Sat": "06:00–18:00","Sun": "06:00–18:00"},
                        "price": {"adult": 400.0, "child": 200.0, "currency": "JPY"},
                        "coords": {"lat": 34.9949, "lon": 135.7850},
                        "source_urls": ["https://www.kiyomizudera.or.jp/en/"],
                    },
                ],
                "sources": ["mock://kyoto-poi"]
            }
        }
    }

    # Restaurants
    state["restaurants"] = {
        "names_by_city": {
            "Tokyo": {
                "Tokyo National Museum": [
                    {"name": "Museum Cafe & Restaurant", "source": "mock:list", "url": "https://example.com/tokyo-museum-cafe"},
                    {"name": "Ueno Sushi", "source": "mock:list"}
                ],
                "Ueno Park": [
                    {"name": "Ueno Park Teahouse", "source": "mock:list"},
                    {"name": "Sakura Bistro", "source": "mock:list", "url": "https://example.com/sakura-bistro"}
                ],
            },
            "Kyoto": {
                "Fushimi Inari Shrine": [
                    {"name": "Torii Ramen", "source": "mock:list"},
                    {"name": "Inari Tea", "source": "mock:list"}
                ],
                "Kiyomizu-dera": [
                    {"name": "Otowa Restaurant", "source": "mock:list", "url": "https://example.com/otowa"},
                    {"name": "Kiyomizu Sweets", "source": "mock:list"}
                ],
            }
        },
        "links_by_city": {
            "Tokyo": {
                "Ueno Park": [
                    {"name": "Parkside Cafe", "url": "https://example.com/parkside", "near_poi": "Ueno Park", "snippet": "Light meals & coffee"}
                ]
            },
            "Kyoto": {
                "Kiyomizu-dera": [
                    {"name": "View Terrace", "url": "https://example.com/view-terrace", "near_poi": "Kiyomizu-dera"}
                ]
            }
        },
        "details_by_city": {}
    }

    # City fares
    state["city_fares"] = {
        "city_fares": {
            "Tokyo": {
                "transit": {
                    "single": {"amount": 220.0, "currency": "JPY"},
                    "day_pass": {"amount": 900.0, "currency": "JPY"},
                    "weekly_pass": None
                },
                "taxi": {"base": 500.0, "per_km": 280.0, "per_min": 0.0, "currency": "JPY"},
            },
            "Kyoto": {
                "transit": {
                    "single": {"amount": 210.0, "currency": "JPY"},
                    "day_pass": {"amount": 700.0, "currency": "JPY"},
                    "weekly_pass": None
                },
                "taxi": {"base": 500.0, "per_km": 300.0, "per_min": 0.0, "currency": "JPY"},
            }
        }
    }

    # Intercity (optional)
    state["intercity"] = {
        "hops": [
            {"from": "Tokyo", "to": "Kyoto", "mode": None, "duration": None, "price": None, "currency": None}
        ]
    }

    # Interpreter-like context
    state.setdefault("interp", {})
    state["interp"]["dates"] = {"start": "2025-04-10", "end": "2025-04-18"}
    state["interp"]["travelers"] = {"adults": 2, "children": 0}
    state["interp"]["preferences"] = {"language": "en"}

# ---------------- Final router (split: node + decider) ----------------
FINAL_ORDER = ["disc.costs", "geo.assemble", "opt.greedy", "trip.maker"]


def final_gate(state: TravelState) -> TravelState:
    """No-op initializer; keep for symmetry & logging."""
    state.setdefault("final_done", [])
    if not state.get("logs"):
        state["logs"] = []
    state["logs"].append("[final.gate] ready")
    return state

def final_decider(state: TravelState) -> str:
    """Pure router: pick the first step not in final_done. Do NOT mutate state here."""
    done = set(state.get("final_done") or [])
    for step in FINAL_ORDER:
        if step not in done:
            state["last_tool"] = step  # harmless to set; router can write small updates
            return step
    return END

# ---------------- Final tool nodes ----------------
def node_disc_costs(state: TravelState) -> TravelState:
    try:
        req = {
            "cities": state.get("cities") or [],
            "dates": (state.get("interp") or {}).get("dates") or {},
            "assumptions": {"rides_per_day": 2},
            "poi": state.get("poi") or {},
            "restaurants": state.get("restaurants") or {},
            "city_fares": state.get("city_fares") or {},
            "intercity": state.get("intercity") or {},
            "fx": state.get("fx") or {},
            "preferences": (state.get("interp") or {}).get("preferences") or {},
            "travelers": (state.get("interp") or {}).get("travelers") or {"adults": 2, "children": 0},
        }
        print(f"this is req: {req}")
        app_state = type("AppState", (), {})()
        app_state.request = req
        app_state.logs = []
        app_state.meta = {}

        res = discovery_and_cost(app_state)
        state["discovery"] = res.request.get("discovery") or {}
        state.setdefault("logs", []).append("[disc.costs] ok")
    except Exception as e:
        state.setdefault("errors", []).append(f"disc.costs: {e}")
        state.setdefault("logs", []).append(f"[disc.costs] ERROR: {e}")
    finally:
        state.setdefault("final_done", []).append("disc.costs")
    return state

def node_geo_assemble(state: TravelState) -> TravelState:
    try:
        req = {
            "discovery": state.get("discovery") or {},
            "fx": state.get("fx") or {},
        }
        app_state = type("AppState", (), {})()
        app_state.request = req
        app_state.logs = []
        app_state.meta = {}

        res = geocost_assembler(app_state)
        state["geocost"] = res.request.get("geocost") or {}
        state.setdefault("logs", []).append("[geo.assemble] ok")
    except Exception as e:
        state.setdefault("errors", []).append(f"geo.assemble: {e}")
        state.setdefault("logs", []).append(f"[geo.assemble] ERROR: {e}")
    finally:
        state.setdefault("final_done", []).append("geo.assemble")
    return state

def node_opt_greedy(state: TravelState) -> TravelState:
    try:
        req = {
            "geocost": state.get("geocost") or {},
            "discovery": state.get("discovery") or {},
            "dates": (state.get("interp") or {}).get("dates") or {},
            "preferences": (state.get("interp") or {}).get("preferences") or {},
        }
        app_state = type("AppState", (), {})()
        app_state.request = req
        app_state.logs = []
        app_state.meta = {}

        res = itinerary_optimizer_greedy(app_state)
        state["itinerary"] = res.request.get("itinerary") or {}
        state.setdefault("logs", []).append("[opt.greedy] ok")
    except Exception as e:
        state.setdefault("errors", []).append(f"opt.greedy: {e}")
        state.setdefault("logs", []).append(f"[opt.greedy] ERROR: {e}")
    finally:
        state.setdefault("final_done", []).append("opt.greedy")
    return state

def node_trip_maker(state: TravelState) -> TravelState:
    try:
        req = {
            "itinerary": state.get("itinerary") or {},
            "discovery": state.get("discovery") or {},
            "geocost": state.get("geocost") or {},
            "fx": state.get("fx") or {},
            "user_message": state.get("user_message") or "",
        }
        app_state = type("AppState", (), {})()
        app_state.request = req
        app_state.logs = []
        app_state.meta = {}

        res = trip_orchestrator(app_state)
        state["trip"] = res.request.get("trip") or {}
        state.setdefault("logs", []).append("[trip.maker] ok")
    except Exception as e:
        state.setdefault("errors", []).append(f"trip.maker: {e}")
        state.setdefault("logs", []).append(f"[trip.maker] ERROR: {e}")
    finally:
        state.setdefault("final_done", []).append("trip.maker")
    return state

# ---------------- Graph ----------------
def build_graph(start: str = "final") -> StateGraph:
    """
    start = "final" -> entry at final.gate (what you asked)
    start = "full"  -> optional: run gap critic first, then final pipeline.
    """
    g = StateGraph(TravelState)

    # final nodes
    g.add_node("final.gate", final_gate)
    g.add_node("disc.costs", node_disc_costs)
    g.add_node("geo.assemble", node_geo_assemble)
    g.add_node("opt.greedy", node_opt_greedy)
    g.add_node("trip.maker", node_trip_maker)

    if start == "final":
        g.set_entry_point("final.gate")
    else:
        if HAVE_GAP:
            g.add_node("gap.search_fill", node_gap_search_fill)
            g.set_entry_point("gap.search_fill")
            g.add_conditional_edges(
                "gap.search_fill",
                cond_gap_more_or_done,
                {
                    "more": "gap.search_fill",
                    "done": "final.gate",
                },
            )
        else:
            g.set_entry_point("final.gate")

    # final.gate → in-order tools via decider
    g.add_conditional_edges(
        "final.gate",
        final_decider,
        {
            "disc.costs": "disc.costs",
            "geo.assemble": "geo.assemble",
            "opt.greedy": "opt.greedy",
            "trip.maker": "trip.maker",
            END: END,
        },
    )

    # each final tool loops back to the gate
    for n in ["disc.costs", "geo.assemble", "opt.greedy", "trip.maker"]:
        g.add_edge(n, "final.gate")

    return g

# --------------- Run / Test helpers ---------------
def run_final_from_mocks(message: str) -> TravelState:
    graph = build_graph(start="final").compile()
    init: TravelState = {"user_message": message}
    _init_lists(init)
    if USE_MOCK:
        _seed_informative_data(init)
    return graph.invoke(init)

if __name__ == "__main__":
    demo = "We’re two adults visiting Japan in April for ~9 days. We love food and museums. Show prices in USD and suggest a plan."
    final_state = run_final_from_mocks(demo)
    print("\n--- FINAL KEYS ---")
    print([k for k in final_state.keys() if k not in ("logs","errors","user_message")])
    print("\nCities:", final_state.get("cities"))
    print("\nTrip keys:", list((final_state.get("trip") or {}).keys()))
    if final_state.get("errors"):
        print("\nErrors:", final_state["errors"])
    print("\nLast 10 logs:")
    for ln in (final_state.get("logs") or [])[-10:]:
        print("  ", ln)
