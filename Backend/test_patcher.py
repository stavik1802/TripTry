# scripts/test_fill_gaps_search_only.py
from app.graph.nodes.gap_data_tool import fill_gaps_search_only

state = {
    "user_message": "Plan Tokyo on a budget.",
    "cities": ["Tokyo"],
    "city_country_map": {"Tokyo": "Japan"},
    "done_tools": ["fares.city"],   # pretend this tool ran
}

missing = [
    {
        "path": "city_fares.Tokyo.transit.day_pass",
        "description": "day pass transit price (adult) with currency",
        "schema": '{"type":"object","properties":{"amount":{"type":"number"},"currency":{"type":"string"}}}',
        "hints": ["day pass","day ticket","official"],
        "context": {"city":"Tokyo","country":"Japan"},
        "allow_source_patch": True,
    }
]

args = {
    "message": state.get("user_message", ""),
    "request_snapshot": state,
    "missing": missing,
    "max_queries_per_item": 4,
    "max_results_per_query": 6,
}

result, patched = fill_gaps_search_only(args)

print("=== ITEMS FILLED ===")
for it in result["items"]:
    print(it)

print("\n=== PATCH KEYS ===")
for k in sorted(result["patches"].keys()):
    print(k)

print("\n=== LOGS (first 10) ===")
for ln in result["logs"][:10]:
    print(ln)

print("\n=== Patched value ===")
print(patched.get("city_fares", {}).get("Tokyo", {}).get("transit", {}).get("day_pass"))
