# scripts/run_end_to_end.py
# Run the full AgentCoordinator graph end-to-end with a single user message.

import os
import json
import argparse
from datetime import datetime

# If you run from repo root:
#   PYTHONPATH=Backend python scripts/run_end_to_end.py "Plan a 3-day trip to Italy"
# If you prefer, adjust imports below if your layout differs.

from app.agents.agent_coordinator import AgentCoordinator
from app.agents.planning_agent import PlanningAgent
from app.agents.reasearch_agent import ResearchAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.gap_agent import GapAgent
from app.agents.output_agent import OutputAgent
from app.agents.learning_agent import LearningAgent

def main():
    parser = argparse.ArgumentParser(description="Run end-to-end trip-planner graph once.")
    parser.add_argument("message", nargs="?", default="give restaurnt in NYC",
                        help="User message to feed into the system.")
    parser.add_argument("--sla", type=int, default=0,
                        help="Optional SLA seconds to speed routing to response (0=off).")
    parser.add_argument("--verbose", action="store_true", help="Print intermediate buckets.")
    args = parser.parse_args()

    # Optional: make it obvious if we’re running without keys (it’s fine; system still works).
    if not os.getenv("OPENAI_API_KEY"):
        print("[INFO] OPENAI_API_KEY not set → OutputAgent may use fallback or return minimal text.")
    if not os.getenv("TAVILY_API_KEY"):
        print("[INFO] TAVILY_API_KEY not set → GapAgent’s web gap filler will be limited/fallback.")

    # 1) Coordinator + agents
    coord = AgentCoordinator()
    coord.register_agent("planning_agent",  PlanningAgent())
    coord.register_agent("research_agent",  ResearchAgent())
    coord.register_agent("budget_agent",    BudgetAgent())
    coord.register_agent("gap_agent",       GapAgent())
    coord.register_agent("output_agent",    OutputAgent())
    coord.register_agent("learning_agent",  LearningAgent())

    # 2) Build the graph
    app = coord.build_agent_graph()

    # 3) Initial state
    state = coord.create_initial_state(
        user_request=args.message,
        user_id="demo-user",
        context=None,
    )
    if args.sla > 0:
        state["sla_seconds"] = args.sla

    print("\n=== RUN INFO ===")
    print(f"Message: {args.message!r}")
    if args.sla: print(f"SLA: {args.sla}s")
    print("===============")

    # 4) Invoke graph
    t0 = datetime.now()
    final_state = app.invoke(state)
    dt = (datetime.now() - t0).total_seconds()

    # 5) Print results
    final = final_state.get("final_response")
    learning = final_state.get("learning_insights") or final_state.get("learning_analysis")

    print("\n=== FINAL RESPONSE ===")
    if isinstance(final, dict):
        # Many OutputAgent variants return {"status": "...", "response": {...}} or {"summary":..., ...}
        # Try a few common fields to show helpful text.
        response_text = None
        if "response" in final and isinstance(final["response"], dict):
            # shaper where OutputAgent puts "response_text" or similar
            response_text = final["response"].get("response_text") or final["response"].get("text")
        if not response_text:
            response_text = final.get("response_text") or final.get("summary") or json.dumps(final, indent=2)
        print(response_text)
    else:
        print(final or "(no final response)")

    print("\n=== TIMING ===")
    print(f"Total runtime: {dt:.2f}s")

    if args.verbose:
        print("\n=== PLANNING DATA ===")
        print(json.dumps(final_state.get("planning_data", {}), indent=2, ensure_ascii=False))

        print("\n=== RESEARCH DATA ===")
        print(json.dumps(final_state.get("research_data", {}), indent=2, ensure_ascii=False))

        print("\n=== BUDGET DATA ===")
        print(json.dumps(final_state.get("budget_data", {}), indent=2, ensure_ascii=False))

        if learning:
            print("\n=== LEARNING INSIGHTS ===")
            print(json.dumps(learning, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()



# # run_budget_agent_test.py
# # Self-contained harness to test BudgetAgent when "city_graph" tool is missing/present.

# from types import SimpleNamespace

# # ---- Import your agent & constants
# from app.agents.budget_agent import BudgetAgent, STANDARD_TOOL_NAMES

# # ---- Minimal stubs for the graph bridge + context
# class DummyBridge:
#     def __init__(self, available):
#         # This is what your agent checks!
#         self.available_tools = available

#     def execute_tool(self, tool_name: str, payload: dict):
#         print(f"[DummyBridge] execute_tool: {tool_name}")
#         # Simulate each tool's minimal expected shape
#         if tool_name == STANDARD_TOOL_NAMES["discoveries_costs"]:
#             # Must return {"status":"success","result":{...}}
#             return {
#                 "status": "success",
#                 "result": {
#                     # Whatever your code stores as budget_data:
#                     "request": {"trip": {"budget": {"total": 1234}, "totals": {}}}
#                 }
#             }

#         if tool_name == STANDARD_TOOL_NAMES["city_graph"]:
#             # Your agent expects "result.request.geocost"
#             return {
#                 "status": "success",
#                 "result": {
#                     "request": {
#                         "geocost": {
#                             "Tokyo": {"pois": ["Senso-ji"], "fares": {"single": 2.5}},
#                             "Kyoto": {"pois": ["Fushimi Inari"], "fares": {"day_pass": 6.0}},
#                         }
#                     }
#                 }
#             }

#         if tool_name == STANDARD_TOOL_NAMES["optimizer"]:
#             return {
#                 "status": "success",
#                 "result": {
#                     "optimized": True,
#                     "note": "dummy optimizer output"
#                 }
#             }

#         if tool_name == STANDARD_TOOL_NAMES["trip_maker"]:
#             # Must return "success" with a trip structure your OutputAgent can read
#             return {
#                 "status": "success",
#                 "result": {
#                     "request": {
#                         "trip": {
#                             "days": [
#                                 {"date": "Day 1", "city": "Tokyo", "items": []},
#                                 {"date": "Day 2", "city": "Kyoto", "items": []},
#                             ]
#                         }
#                     }
#                 }
#             }

#         return {"status": "error", "error": f"Unknown tool {tool_name}"}


# class DummyContext:
#     """Mimics AgentContext with only what BudgetAgent uses."""
#     def __init__(self, research_ok=True):
#         # Minimal shapes to pass your validation:
#         self.shared_data = {
#             "planning_data": {
#                 "countries": [{"country": "Japan", "cities": ["Tokyo", "Kyoto"]}],
#                 "travelers": {"adults": 1, "children": 0},
#                 "musts": [],
#                 "preferences": {"duration_days": 5},
#                 "dates": {},
#             },
#             "research_data": {
#                 "cities": ["Tokyo", "Kyoto"] if research_ok else [],
#                 "poi": {"poi_by_city": {"Tokyo": {"pois": [{"name": "Senso-ji"}]},
#                                          "Kyoto": {"pois": [{"name": "Fushimi Inari"}]}}},
#                 "restaurants": {"names_by_city": {"Tokyo": [{"name": "Ichiran"}],
#                                                   "Kyoto": [{"name": "Ippudo"}]}},
#                 "city_fares": {"city_fares": {"Tokyo": {"single": 2.5}, "Kyoto": {"day_pass": 6.0}}},
#                 "intercity": {"hops": [{"from": "Tokyo", "to": "Kyoto", "mode": "Shinkansen"}]},
#                 "fx": {"JPY": 150.0},
#             },
#         }
#         self.user_request = "Make me a 5-day trip."

# # ---- Helper to run the agent once with a given available toolset
# def run_case(title: str, available_tools: list):
#     print("\n" + "="*70)
#     print(f"[CASE] {title}")
#     print("="*70)

#     agent = BudgetAgent()
#     # Inject our dummy bridge
#     agent.graph_bridge = DummyBridge(available=available_tools)

#     ctx = DummyContext()
#     result = agent.execute_task(ctx)
#     print("\n[Result]")
#     print(result)

#     # Show what got written back into shared_data
#     print("\n[Shared Data Keys]")
#     print(list(ctx.shared_data.keys()))
#     for k in ("budget_data", "geocost_data", "optimized_data", "trip_data"):
#         if k in ctx.shared_data:
#             print(f"- {k}: present")
#         else:
#             print(f"- {k}: MISSING")


# if __name__ == "__main__":
#     # Tool names your agent expects (print once for clarity)
#     print("[STANDARD_TOOL_NAMES]")
#     for k, v in STANDARD_TOOL_NAMES.items():
#         print(f"  {k} -> {v}")

#     # 1) City graph missing: expect early return "City graph tool not available"
#     run_case(
#         "Missing city_graph tool",
#         available_tools=[
#             STANDARD_TOOL_NAMES["discoveries_costs"],
#             # STANDARD_TOOL_NAMES["city_graph"]      <-- purposely omitted
#             STANDARD_TOOL_NAMES["optimizer"],
#             STANDARD_TOOL_NAMES["trip_maker"],
#         ],
#     )

#     # 2) All tools present: expect full success with trip_data
#     run_case(
#         "All tools present",
#         available_tools=[
#             STANDARD_TOOL_NAMES["discoveries_costs"],
#             STANDARD_TOOL_NAMES["city_graph"],
#             STANDARD_TOOL_NAMES["optimizer"],
#             STANDARD_TOOL_NAMES["trip_maker"],
#         ],
#     )
