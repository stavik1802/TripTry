# app/tools/city_recommender_main.py
from __future__ import annotations
import os, time, json
from typing import Dict, Any, List

# Import your tool + schemas
from app.graph.nodes.city_recommender_tool import (
    city_recommender_tool,
    CityRecommenderArgs,
    CountryArg,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def run_case(name: str, args: CityRecommenderArgs) -> Dict[str, Any]:
    t0 = time.time()
    try:
        res = city_recommender_tool(args)
        took = time.time() - t0
        print(f"\n===== {name} =====")
        print(f"took: {took:.2f}s | C={res.recommended_city_count} | cities={res.cities}")
        # per-country stats (seeds/pages/kept)
        for ctry, st in (res.stats or {}).items():
            print(f"  - {ctry}: seeds={st.get('seeds')} pages={st.get('pages')} kept={st.get('kept')}")
        # top candidates (first 5)
        top = res.city_candidates[:5]
        if top:
            print("  top candidates:")
            for c in top:
                print(f"    • {c.city} ({c.country})  score={c.score}")
        # a couple of log lines
        if res.logs:
            print("  logs:")
            for ln in res.logs[:5]:
                print(f"    {ln}")
        # light sanity
        assert len(res.cities) >= 1, "expected at least one city"
        return {"ok": True, "result": res}
    except Exception as e:
        took = time.time() - t0
        print(f"\n===== {name} (ERROR) =====\nfailed in {took:.2f}s: {e}")
        return {"ok": False, "error": str(e)}

def env_info():
    print("FAST_TEST:", os.getenv("CITYREC_FAST_TEST", "0"))
    print("TAVILY_API_KEY:", "set" if os.getenv("TAVILY_API_KEY") else "MISSING")
    print("OPENAI_API_KEY:", "set" if os.getenv("OPENAI_API_KEY") else "MISSING")
    # Speedy defaults (override here if you want)
    os.environ.setdefault("CITYREC_SEARCH_DEPTH", "advanced")
    os.environ.setdefault("CITYREC_CHUNKS_PER_SOURCE", "2")
    os.environ.setdefault("CITYREC_MAX_RESULTS_PER_QUERY", "5")
    os.environ.setdefault("CITYREC_MAX_QUERIES_PER_COUNTRY", "3")
    os.environ.setdefault("CITYREC_MAX_PAGES_PER_COUNTRY", "8")
    os.environ.setdefault("CITYREC_MAX_SEARCH_PAGES", "6")
    os.environ.setdefault("CITYREC_SEARCH_TIMEOUT_SEC", "8")
    os.environ.setdefault("CITYREC_EXTRACT_TIMEOUT_SEC", "8")
    os.environ.setdefault("CITYREC_COUNTRY_DEADLINE_SEC", "16")
    os.environ.setdefault("CITYREC_MAX_EXTRACT_FALLBACK", "3")

# -------------------------------------------------------------------
# Prebuilt test scenarios
# -------------------------------------------------------------------
def case_japan_with_dates() -> CityRecommenderArgs:
    # 9-day trip → should suggest ~3–4 cities depending on pace
    return CityRecommenderArgs(
        countries=[CountryArg(country="Japan")],
        dates={"start": "2025-04-10", "end": "2025-04-18"},
        travelers={"adults": 2, "children": 0},
        musts=[],                       # add ["Tokyo"] to force include
        preferred_cities=["Kyoto"],     # light boost
        preferences={"themes": ["food", "museums"], "pace": "normal"},
        default_recommend_count=5,
        max_candidates=12,
    )

def case_multi_country_sp_it() -> CityRecommenderArgs:
    # no dates → default_recommend_count used (5)
    return CityRecommenderArgs(
        countries=[CountryArg(country="Spain"), CountryArg(country="Italy")],
        travelers={"adults": 2, "children": 1},
        musts=["Barcelona"],                 # force Barcelona if plausible
        preferred_cities=["Florence", "Seville"],
        preferences={"pace": "fast"},
        default_recommend_count=5,
        max_candidates=12,
    )

def case_given_cities_keep() -> CityRecommenderArgs:
    # user already mentioned cities; ensure they’re retained if plausible
    return CityRecommenderArgs(
        countries=[CountryArg(country="France", cities=["Paris", "Lyon"])],
        travelers={"adults": 1, "children": 0},
        musts=["Paris"],
        preferences={"pace": "slow"},
        default_recommend_count=3,
        max_candidates=10,
    )

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("=== City Recommender quick tests ===")
    env_info()

    tests = [
        ("Japan (dates, themed)", case_japan_with_dates()),
        ("Spain+Italy (multi-country)", case_multi_country_sp_it()),
        ("France (keep given cities)", case_given_cities_keep()),
    ]

    results: List[Dict[str, Any]] = []
    for name, args in tests:
        out = run_case(name, args)
        results.append({"name": name, **out})

    # Short JSON summary at the end (only names + success + first 3 cities)
    summary = []
    for r in results:
        row = {"name": r["name"], "ok": r["ok"]}
        if r["ok"]:
            row["sample_cities"] = r["result"].cities[:3]
        else:
            row["error"] = r["error"]
        summary.append(row)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
