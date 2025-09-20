#!/usr/bin/env python3
"""
Test the complete agent workflow to verify gap agent patches flow to budget agent
"""

import os
import sys
import asyncio
from typing import Dict, Any

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.agents.agent_coordinator import AgentCoordinator
from app.agents.planning_agent import PlanningAgent
from app.agents.reasearch_agent import ResearchAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.gap_agent import GapAgent
from app.agents.output_agent import OutputAgent

# Set API keys
os.environ["OPENAI_API_KEY"] = "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"
os.environ["TAVILY_API_KEY"] = "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"


def create_test_coordinator():
    """Create a test coordinator with all agents registered"""
    coordinator = AgentCoordinator()
    
    # Register all agents
    coordinator.register_agent("planning_agent", PlanningAgent())
    coordinator.register_agent("research_agent", ResearchAgent())
    coordinator.register_agent("budget_agent", BudgetAgent())
    coordinator.register_agent("gap_agent", GapAgent())
    coordinator.register_agent("output_agent", OutputAgent())
    
    return coordinator


def test_gap_to_budget_flow():
    """Test that gap agent patches flow correctly to budget agent"""
    print("🔄 Testing Gap Agent → Budget Agent Data Flow...")
    print("=" * 60)
    
    coordinator = create_test_coordinator()
    
    # Create initial state with incomplete research data that will trigger gaps
    initial_state = coordinator.create_initial_state(
        user_request="Plan a 2-day trip to Paris. I want to visit the Eiffel Tower and Louvre Museum.",
        user_id="test-user"
    )
    
    # Manually set up research data with gaps (simulating what research agent would produce)
    initial_state["research_data"] = {
        "cities": ["Paris"],
        "city_country_map": {"Paris": "France"},
        "poi": {
            "poi_by_city": {
                "Paris": {
                    "pois": [
                        {
                            "name": "Eiffel Tower",
                            # Missing price, hours, coords - will trigger gaps
                        },
                        {
                            "name": "Louvre Museum",
                            # Missing price, hours, coords - will trigger gaps
                        }
                    ]
                }
            }
        },
        "restaurants": {
            "names_by_city": {
                "Paris": ["Café de Flore", "Le Comptoir du Relais"]
            },
            "links_by_city": {
                "Paris": {}  # Missing links - will trigger gaps
            }
        },
        "city_fares": {
            "city_fares": {
                "Paris": {}  # Missing fare data - will trigger gaps
            }
        }
    }
    
    # Set planning data
    initial_state["planning_data"] = {
        "countries": [{"country": "France", "cities": ["Paris"]}],
        "travelers": {"adults": 2, "children": 0},
        "dates": {"start": "2024-06-01", "end": "2024-06-03"},
        "preferences": {"pace": "normal", "budget": "medium"},
        "musts": ["Eiffel Tower", "Louvre Museum"],
        "tool_plan": ["poi_discovery", "restaurants_discovery", "city_fare"]
    }
    
    print("Initial research data (with gaps):")
    print(f"  Cities: {initial_state['research_data']['cities']}")
    print(f"  POIs: {len(initial_state['research_data']['poi']['poi_by_city']['Paris']['pois'])}")
    for poi in initial_state['research_data']['poi']['poi_by_city']['Paris']['pois']:
        print(f"    - {poi['name']}: price={poi.get('price')}, hours={poi.get('hours')}")
    
    print(f"  Restaurants: {len(initial_state['research_data']['restaurants']['names_by_city']['Paris'])}")
    print(f"  City fares: {len(initial_state['research_data']['city_fares']['city_fares']['Paris'])}")
    
    # Build and run the agent graph
    graph = coordinator.build_agent_graph()
    
    print(f"\n🚀 Running agent workflow...")
    print("=" * 40)
    
    try:
        # Run the graph
        final_state = graph.invoke(initial_state)
        
        print(f"\n📊 Final Results:")
        print("=" * 40)
        
        # Check if gap agent was called and filled data
        if "gap_filling_completed" in final_state:
            print(f"✅ Gap filling completed: {final_state['gap_filling_completed']}")
        
        # Check research data after gap filling
        research_data = final_state.get("research_data", {})
        print(f"\nResearch data after gap filling:")
        print(f"  Cities: {research_data.get('cities', [])}")
        
        pois = research_data.get("poi", {}).get("poi_by_city", {}).get("Paris", {}).get("pois", [])
        print(f"  POIs: {len(pois)}")
        for poi in pois:
            print(f"    - {poi.get('name')}: price={poi.get('price')}, hours={poi.get('hours')}")
            if poi.get('coords'):
                print(f"      Coords: {poi.get('coords')}")
            if poi.get('official_url'):
                print(f"      URL: {poi.get('official_url')}")
        
        restaurants = research_data.get("restaurants", {}).get("names_by_city", {}).get("Paris", [])
        print(f"  Restaurants: {len(restaurants)}")
        for restaurant in restaurants[:3]:  # Show first 3
            print(f"    - {restaurant}")
        
        # Check if budget agent received the patched data
        budget_data = final_state.get("budget_data", {})
        print(f"\nBudget data received by budget agent:")
        print(f"  Budget data keys: {list(budget_data.keys()) if budget_data else 'None'}")
        
        trip_data = final_state.get("trip_data", {})
        print(f"\nTrip data created by budget agent:")
        print(f"  Trip data keys: {list(trip_data.keys()) if trip_data else 'None'}")
        
        # Check agent statuses
        print(f"\nAgent statuses:")
        for agent_id, status in final_state.get("agent_statuses", {}).items():
            print(f"  {agent_id}: {status.status} - {status.current_task}")
        
        # Check if there were any errors
        error_agents = [aid for aid, s in final_state.get("agent_statuses", {}).items() if s.status == "error"]
        if error_agents:
            print(f"\n❌ Agents with errors: {error_agents}")
            for agent_id in error_agents:
                error_msg = final_state["agent_statuses"][agent_id].error_message
                print(f"  {agent_id}: {error_msg}")
        else:
            print(f"\n✅ All agents completed successfully!")
        
        return final_state
        
    except Exception as e:
        print(f"\n💥 Workflow failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_manual_gap_budget_flow():
    """Test gap agent and budget agent manually to verify data flow"""
    print("\n🔧 Testing Manual Gap → Budget Flow...")
    print("=" * 50)
    
    from app.agents.base_agent import AgentContext
    
    # Create gap agent
    gap_agent = GapAgent()
    
    # Create context with gaps
    ctx = AgentContext(
        session_id="test-gap-budget-flow",
        user_request="Plan a trip to Paris with Eiffel Tower",
        conversation_history=[],
        shared_data={
            "research_data": {
                "cities": ["Paris"],
                "city_country_map": {"Paris": "France"},
                "poi": {
                    "poi_by_city": {
                        "Paris": {
                            "pois": [
                                {
                                    "name": "Eiffel Tower",
                                    # Missing fields - will trigger gaps
                                }
                            ]
                        }
                    }
                }
            },
            "planning_data": {
                "countries": [{"country": "France", "cities": ["Paris"]}],
                "musts": ["Eiffel Tower"],
                "tool_plan": ["poi_discovery"]
            }
        },
        goals=[],
        constraints={}
    )
    
    print("Before gap filling:")
    pois = ctx.shared_data["research_data"]["poi"]["poi_by_city"]["Paris"]["pois"]
    print(f"  POIs: {len(pois)}")
    for poi in pois:
        print(f"    - {poi.get('name')}: price={poi.get('price')}, hours={poi.get('hours')}")
    
    # Run gap agent
    print(f"\n🔧 Running gap agent...")
    gap_result = gap_agent.execute_task(ctx)
    print(f"Gap result: {gap_result.get('status')} - {gap_result.get('filled_items', 0)} items filled")
    
    print("\nAfter gap filling:")
    pois = ctx.shared_data["research_data"]["poi"]["poi_by_city"]["Paris"]["pois"]
    print(f"  POIs: {len(pois)}")
    for poi in pois:
        print(f"    - {poi.get('name')}: price={poi.get('price')}, hours={poi.get('hours')}")
        if poi.get('coords'):
            print(f"      Coords: {poi.get('coords')}")
    
    # Now test budget agent with the patched data
    print(f"\n💰 Running budget agent with patched data...")
    budget_agent = BudgetAgent()
    budget_result = budget_agent.execute_task(ctx)
    
    print(f"Budget result: {budget_result.get('status')}")
    print(f"Budget data keys: {list(budget_result.get('budget_data', {}).keys())}")
    print(f"Trip data keys: {list(budget_result.get('trip_data', {}).keys())}")
    
    return gap_result, budget_result


def main():
    """Run the complete workflow tests"""
    print("🧪 Agent Workflow Integration Test")
    print("=" * 60)
    
    try:
        # Test 1: Complete workflow
        print("Test 1: Complete Agent Workflow")
        final_state = test_gap_to_budget_flow()
        
        # Test 2: Manual gap → budget flow
        print("\nTest 2: Manual Gap → Budget Flow")
        gap_result, budget_result = test_manual_gap_budget_flow()
        
        # Summary
        print(f"\n📊 Test Summary:")
        print(f"  Complete workflow: {'✅ PASSED' if final_state else '❌ FAILED'}")
        print(f"  Gap agent: {gap_result.get('status')} ({gap_result.get('filled_items', 0)} items)")
        print(f"  Budget agent: {budget_result.get('status')}")
        
        if final_state and gap_result.get('status') == 'success' and budget_result.get('status') == 'success':
            print(f"\n🎉 All tests PASSED - Gap agent patches flow correctly to budget agent!")
        else:
            print(f"\n❌ Some tests FAILED")
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
