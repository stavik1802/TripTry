#!/usr/bin/env python3
"""
Manual gap test - directly calls gap detection functions to understand the logic
"""

import os
import sys

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext
from app.graph.gap.specs import _missing_pois, _missing_restaurants, _missing_city_fares

# Set API keys
os.environ["OPENAI_API_KEY"] = "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"
os.environ["TAVILY_API_KEY"] = "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"


def test_direct_gap_detection():
    """Test gap detection functions directly"""
    print("🔍 Testing Direct Gap Detection Functions...")
    
    # Create state that should trigger gaps
    state = {
        "cities": ["Paris"],
        "city_country_map": {"Paris": "France"},
        "done_tools": ["poi.discovery", "restaurants.discovery", "fares.city"],  # Use dot notation
        "poi": {
            "poi_by_city": {
                "Paris": {
                    "pois": [
                        {
                            "name": "Eiffel Tower",
                            # Missing price, hours, coords - should trigger gaps
                        },
                        {
                            "name": "Louvre Museum",
                            # Missing price, hours, coords - should trigger gaps
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
                "Paris": {}  # Missing links - should trigger gaps
            },
            "details_by_city": {
                "Paris": {}  # Missing details - should trigger gaps
            }
        },
        "city_fares": {
            "city_fares": {
                "Paris": {
                    "transit": {},  # Missing transit data
                    "taxi": {}      # Missing taxi data
                }
            }
        }
    }
    
    print("Testing POI gap detection...")
    poi_gaps = _missing_pois(state)
    print(f"POI gaps found: {len(poi_gaps)}")
    for gap in poi_gaps:
        print(f"  - {gap.get('path')}: {gap.get('description')}")
    
    print("\nTesting restaurant gap detection...")
    restaurant_gaps = _missing_restaurants(state)
    print(f"Restaurant gaps found: {len(restaurant_gaps)}")
    for gap in restaurant_gaps:
        print(f"  - {gap.get('path')}: {gap.get('description')}")
    
    print("\nTesting city fares gap detection...")
    city_fare_gaps = _missing_city_fares(state)
    print(f"City fare gaps found: {len(city_fare_gaps)}")
    for gap in city_fare_gaps:
        print(f"  - {gap.get('path')}: {gap.get('description')}")
    
    return poi_gaps + restaurant_gaps + city_fare_gaps


def test_gap_agent_with_proper_done_tools():
    """Test gap agent with proper done_tools format"""
    print("\n🔧 Testing Gap Agent with Proper done_tools...")
    
    agent = GapAgent()
    
    # Create context with proper done_tools format
    ctx = AgentContext(
        session_id="test-proper-done-tools",
        user_request="Find details for Paris POIs and restaurants",
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
                                    # Missing price, hours, coords
                                }
                            ]
                        }
                    }
                },
                "restaurants": {
                    "names_by_city": {
                        "Paris": ["Café de Flore"]
                    },
                    "links_by_city": {
                        "Paris": {}  # Missing links
                    }
                }
            },
            "planning_data": {
                "countries": [{"country": "France", "cities": ["Paris"]}],
                "musts": ["Eiffel Tower"],
                "tool_plan": ["poi_discovery", "restaurants_discovery"]
            },
            "done_tools": ["poi.discovery", "restaurants.discovery"]  # Add done_tools to shared_data
        },
        goals=[],
        constraints={}
    )
    
    print("Before gap filling:")
    pois = ctx.shared_data["research_data"]["poi"]["poi_by_city"]["Paris"]["pois"]
    print(f"  POIs: {len(pois)}")
    for poi in pois:
        print(f"    - {poi.get('name')}: price={poi.get('price')}, hours={poi.get('hours')}")
    
    # Execute gap filling
    result = agent.execute_task(ctx)
    
    print(f"\nGap filling result: {result.get('status')}")
    print(f"Filled items: {result.get('filled_items', 0)}")
    print(f"Patches applied: {result.get('patches_applied', 0)}")
    
    # Check results
    pois = ctx.shared_data["research_data"]["poi"]["poi_by_city"]["Paris"]["pois"]
    print(f"\nAfter gap filling:")
    print(f"  POIs: {len(pois)}")
    for poi in pois:
        print(f"    - {poi.get('name')}: price={poi.get('price')}, hours={poi.get('hours')}")
    
    return result


def main():
    """Run the manual gap tests"""
    print("🧪 Manual Gap Agent Test - Understanding Gap Detection")
    print("=" * 60)
    
    try:
        # Test 1: Direct gap detection
        all_gaps = test_direct_gap_detection()
        
        if all_gaps:
            print(f"\n✅ Found {len(all_gaps)} gaps using direct detection!")
            
            # Test 2: Gap agent with proper done_tools
            result = test_gap_agent_with_proper_done_tools()
            
            print(f"\n📊 Test Summary:")
            print(f"  Direct gaps detected: {len(all_gaps)}")
            print(f"  Gap agent result: {result.get('status')}")
            print(f"  Items filled: {result.get('filled_items', 0)}")
            
            if result.get('status') == 'success':
                print(f"\n✅ Gap agent successfully processed missing data!")
            else:
                print(f"\n❌ Gap filling failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"\n⚠️  No gaps detected even with direct detection - checking gap detection logic...")
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
