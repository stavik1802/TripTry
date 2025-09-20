# tests/test_travel_graph_routes.py
from types import SimpleNamespace
import pytest

import app.graph.build_graph as tg


# ---------- helpers: tiny stubs & instrumentation ----------

def _ensure_route_list(state):
    state.setdefault("route", [])
    state.setdefault("logs", [])
    state.setdefault("done_tools", [])
    state.setdefault("plan_queue", [])


def _stub_cities(state, cities=None, country="Testland"):
    cities = cities or ["CityA", "CityB"]
    tg._init_lists(state)
    state["cities"] = list(cities)
    state["city_country_map"] = {c: country for c in cities}


def _stub_poi(state):
    cities = state.get("cities") or []
    payload = {"poi_by_city": {}}
    for c in cities:
        payload["poi_by_city"][c] = {"pois": [{"name": f"{c} Museum"}]}
    state["poi"] = payload


def _stub_restaurants(state):
    cities = state.get("cities") or []
    links_by_city = {c: {"center": [{"name": f"{c} Bistro", "url": "https://example.com", "near_poi": "center"}]} for c in cities}
    names_by_city = {c: {"center": [{"name": f"{c} Grill", "source": "https://example.com", "url": None}]} for c in cities}
    state["restaurants"] = {"links_by_city": links_by_city, "names_by_city": names_by_city}


def _stub_city_fares(state):
    cities = state.get("cities") or []
    payload = {"city_fares": {c: {"transit": {}, "taxi": {}} for c in cities}}
    state["city_fares"] = payload


def _stub_intercity(state):
    cities = state.get("cities") or []
    hops = {}
    for i in range(len(cities) - 1):
        a, b = cities[i], cities[i + 1]
        hops[f"{a} -> {b}"] = {"recommended": "train"}
    state["intercity"] = {"hops": hops}


def _stub_fx(state, target="USD"):
    state["fx"] = {
        "provider": "stub",
        "target": target,
        "to_target": {"USD": 1.0, "EUR": 1.0, "JPY": 0.007},
        "currency_by_country": {},
    }
    state["fx_meta"] = {
        "target": target,
        "to_target": state["fx"]["to_target"],
        "currency_by_country": {},
    }


def _wrap_router(monkeypatch):
    orig = tg.router

    def router_wrapper(state):
        _ensure_route_list(state)
        nxt = orig(state)
        state["route"].append(f"router→{nxt}")
        return nxt

    monkeypatch.setattr(tg, "router", router_wrapper)


def _wrap_replan(monkeypatch):
    orig = tg.node_replan

    def replan_wrapper(state):
        _ensure_route_list(state)
        state["route"].append("replan")
        return orig(state)

    monkeypatch.setattr(tg, "node_replan", replan_wrapper)


def _wrap_node(monkeypatch, name, body):
    """
    Replace node_* with a wrapper that logs the node name, executes a small stub body,
    marks it done, and returns the state.
    """
    def wrapper(state):
        _ensure_route_list(state)
        state["route"].append(name)
        body(state)
        state["done_tools"].append(name)
        state["logs"].append(f"[{name}] stub ok")
        return state

    monkeypatch.setattr(tg, f"node_{name.replace('.', '_') if name != 'fx.oracle' else 'fx_oracle'}", wrapper)


def _stub_interpret(monkeypatch, interp_dict):
    """
    Bypass real interpreter & external deps: set interp directly and compute initial plan.
    """
    def node_interpret_stub(state):
        _ensure_route_list(state)
        state["route"].append("interpret")
        # snapshot "interp" just like the real node
        state["interp"] = interp_dict
        state["countries"] = interp_dict.get("countries") or []
        state["cities"] = [c for c in tg._flatten_cities(interp_dict)]
        state["city_country_map"] = tg._mk_city_country_map(interp_dict)
        state["plan_queue"] = tg._compute_next_plan(state)
        state["logs"].append(f"[interpret/stub] intent={interp_dict.get('intent')} plan={state['plan_queue']}")
        return state

    monkeypatch.setattr(tg, "node_interpret", node_interpret_stub)


def _compile_graph_with_instrumentation(monkeypatch, interp_dict,
                                        stub_map=None):
    """
    stub_map: dict of {tool_name: callable(state)} to update state for each tool node.
    """
    _wrap_router(monkeypatch)
    _wrap_replan(monkeypatch)
    _stub_interpret(monkeypatch, interp_dict)

    # default stubs for all known tools
    defaults = {
        "cities.recommender": lambda s: _stub_cities(s, cities=["CityA", "CityB"], country="Demo"),
        "fx.oracle":         lambda s: _stub_fx(s, target=(interp_dict.get("target_currency") or "EUR")),
        "fares.city":        _stub_city_fares,
        "fares.intercity":   _stub_intercity,
        "poi.discovery":     _stub_poi,
        "restaurants.discovery": _stub_restaurants,
    }
    if stub_map:
        defaults.update(stub_map)

    for tool_name, body in defaults.items():
        _wrap_node(monkeypatch, tool_name, body)

    return tg.build_graph().compile()


# ---------- scenarios ----------

def _interp_base(intent, countries, cities_by_country=None, target="EUR", tool_plan=None, extras=None):
    ci = []
    for country in countries:
        entry = {"country": country, "cities": []}
        if cities_by_country and country in cities_by_country:
            entry["cities"] = cities_by_country[country]
        ci.append(entry)
    d = {
        "intent": intent,
        "countries": ci,
        "dates": {},
        "travelers": {"adults": 1, "children": 0},
        "musts": [],
        "preferences": {},
        "budget_caps": {},
        "target_currency": target,
        "requires": [],
        "tool_plan": tool_plan or [],
        "notes": [],
    }
    if extras:
        d.update(extras)
    return d


# ---------- tests ----------

def test_route_recommend_cities(monkeypatch):
    interp = _interp_base(
        intent="recommend_cities",
        countries=["Japan"],
        tool_plan=["cities.recommender", "writer.report"],
    )
    graph = _compile_graph_with_instrumentation(monkeypatch, interp)
    out = graph.invoke({"user_message": "Where should I go in Japan?"})

    # Visible route
    print("\nROUTE:", "  ".join(out["route"]))

    # Assertions: must include recommender then end
    assert out["route"][0] == "interpret"
    assert "cities.recommender" in out["route"]
    assert any(str(tg.END) in step for step in out["route"])


def test_route_poi_lookup_known_city(monkeypatch):
    interp = _interp_base(
        intent="poi_lookup",
        countries=["France"],
        cities_by_country={"France": ["Paris"]},
        tool_plan=["poi.discovery", "writer.report"],
    )
    graph = _compile_graph_with_instrumentation(monkeypatch, interp)
    out = graph.invoke({"user_message": "Things to do in Paris"})
    print("\nROUTE:", "  ".join(out["route"]))

    # Should go straight to POIs and finish
    assert "poi.discovery" in out["route"]
    assert not any("cities.recommender" == x for x in out["route"])


def test_route_city_fares_with_fx(monkeypatch):
    interp = _interp_base(
        intent="city_fares",
        countries=["United States"],
        cities_by_country={"United States": ["New York"]},
        target="USD",
        tool_plan=["fares.city", "writer.report"],  # interpreter forgot FX; graph should insert fx.oracle
    )
    graph = _compile_graph_with_instrumentation(monkeypatch, interp)
    out = graph.invoke({"user_message": "How much is the NYC metro? Show in USD"})
    print("\nROUTE:", "  ".join(out["route"]))

    # Expect fx.oracle before fares.city
    ix_fx = out["route"].index("fx.oracle")
    ix_city = out["route"].index("fares.city")
    assert ix_fx < ix_city


def test_route_intercity_fares_two_cities(monkeypatch):
    interp = _interp_base(
        intent="intercity_fares",
        countries=["Italy"],
        cities_by_country={"Italy": ["Rome", "Florence"]},
        tool_plan=["fares.intercity", "writer.report"],
    )
    graph = _compile_graph_with_instrumentation(monkeypatch, interp)
    out = graph.invoke({"user_message": "Best way Rome to Florence"})
    print("\nROUTE:", "  ".join(out["route"]))

    assert "fares.intercity" in out["route"]
    # Ensure goal satisfied after single hop
    assert any(str(tg.END) in step for step in out["route"])


def test_route_full_plan_trip(monkeypatch):
    # Interpreter gives cities already; plan should queue the four tools and finish when all satisfied
    interp = _interp_base(
        intent="plan_trip",
        countries=["Japan"],
        cities_by_country={"Japan": ["Tokyo", "Kyoto"]},
        tool_plan=[],  # let graph add minimal plan for plan_trip
    )
    graph = _compile_graph_with_instrumentation(monkeypatch, interp)
    out = graph.invoke({"user_message": "Plan 1 week in Japan, cities & POIs & restaurants"})

    print("\nROUTE:", "  ".join(out["route"]))

    # Expect all four tool nodes to appear (order enforced by _compute_next_plan)
    order = ["fares.city", "fares.intercity", "poi.discovery", "restaurants.discovery"]
    positions = [out["route"].index(name) for name in order]
    assert positions == sorted(positions)


def test_route_recommend_cities_then_poi(monkeypatch):
    # No cities initially → recommender must run first; poi afterwards
    interp = _interp_base(
        intent="poi_lookup",
        countries=["Spain"],  # no city provided
        tool_plan=["poi.discovery"],  # interpreter asks for POIs but we have no cities; graph should prepend recommender
    )

    # Make recommender produce 1 city so poi can proceed
    graph = _compile_graph_with_instrumentation(
        monkeypatch,
        interp,
        stub_map={"cities.recommender": lambda s: _stub_cities(s, cities=["Barcelona"], country="Spain")}
    )
    out = graph.invoke({"user_message": "Things to do in Spain"})
    print("\nROUTE:", "  ".join(out["route"]))

    ix_rec = out["route"].index("cities.recommender")
    ix_poi = out["route"].index("poi.discovery")
    assert ix_rec < ix_poi
