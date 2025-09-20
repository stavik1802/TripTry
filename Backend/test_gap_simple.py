#!/usr/bin/env python3
"""
Simple test for GapAgent - tests filling 1-2 specific missing items
"""

import os
import sys

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext

# Set API keys
os.environ["OPENAI_API_KEY"] = "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"
os.environ["TAVILY_API_KEY"] = "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"


def test_poi_gap_filling():
    """Test filling missing POI data for Paris"""
    print("🗼 Testing POI Gap Filling for Paris...")
    
    agent = GapAgent()
    
    # Create context with missing POI data
    ctx = AgentContext(
        session_id="test-poi-gap",
        user_request="I want to visit the Eiffel Tower and Louvre in Paris",
        conversation_history=[],
        shared_data={
            "research_data": {
                "cities": ["Paris"],
                "city_country_map": {"Paris": "France"},
                "poi": {
                    "poi_by_city": {
                        "Paris": {
                            "pois": []  # Empty - should be filled
                        }
                    }
                }
            },
            "planning_data": {
                "countries": [{"country": "France", "cities": ["Paris"]}],
                "musts": ["Eiffel Tower", "Louvre"],
                "tool_plan": ["poi_discovery"]
            }
        },
        goals=[],
        constraints={}
    )
    
    print("Before gap filling:")
    print(f"  POIs in Paris: {len(ctx.shared_data['research_data']['poi']['poi_by_city']['Paris']['pois'])}")
    
    # Execute gap filling
    result = agent.execute_task(ctx)
    
    print(f"\nGap filling result: {result.get('status')}")
    print(f"Filled items: {result.get('filled_items', 0)}")
    print(f"Patches applied: {result.get('patches_applied', 0)}")
    
    # Check results
    pois = ctx.shared_data["research_data"]["poi"]["poi_by_city"]["Paris"]["pois"]
    print(f"\nAfter gap filling:")
    print(f"  POIs in Paris: {len(pois)}")
    
    if pois:
        print("  Found POIs:")
        for poi in pois[:5]:  # Show first 5
            name = poi.get('name', 'Unknown')
            price = poi.get('price', {})
            print(f"    - {name}")
            if price:
                print(f"      Price: {price}")
    
    return result


def test_restaurant_gap_filling():
    """Test filling missing restaurant data for Paris"""
    print("\n🍽️  Testing Restaurant Gap Filling for Paris...")
    
    agent = GapAgent()
    
    # Create context with missing restaurant data
    ctx = AgentContext(
        session_id="test-restaurant-gap",
        user_request="Find good restaurants near the Eiffel Tower in Paris",
        conversation_history=[],
        shared_data={
            "research_data": {
                "cities": ["Paris"],
                "city_country_map": {"Paris": "France"},
                "poi": {
                    "poi_by_city": {
                        "Paris": {
                            "pois": [{"name": "Eiffel Tower"}]
                        }
                    }
                },
                "restaurants": {
                    "names_by_city": {
                        "Paris": []  # Empty - should be filled
                    }
                }
            },
            "planning_data": {
                "countries": [{"country": "France", "cities": ["Paris"]}],
                "musts": ["Eiffel Tower"],
                "tool_plan": ["restaurants_discovery"]
            }
        },
        goals=[],
        constraints={}
    )
    
    print("Before gap filling:")
    restaurants = ctx.shared_data["research_data"]["restaurants"]["names_by_city"]["Paris"]
    print(f"  Restaurants in Paris: {len(restaurants)}")
    
    # Execute gap filling
    result = agent.execute_task(ctx)
    
    print(f"\nGap filling result: {result.get('status')}")
    print(f"Filled items: {result.get('filled_items', 0)}")
    print(f"Patches applied: {result.get('patches_applied', 0)}")
    
    # Check results
    restaurants = ctx.shared_data["research_data"]["restaurants"]["names_by_city"]["Paris"]
    print(f"\nAfter gap filling:")
    print(f"  Restaurants in Paris: {len(restaurants)}")
    
    if restaurants:
        print("  Found restaurants:")
        for restaurant in restaurants[:5]:  # Show first 5
            print(f"    - {restaurant}")
    
    return result


def main():
    """Run the simple gap filling tests"""
    print("🧪 Simple Gap Agent Test - Real API Calls")
    print("=" * 50)
    
    try:
        # Test POI gap filling
        poi_result = test_poi_gap_filling()
        
        # Test restaurant gap filling
        restaurant_result = test_restaurant_gap_filling()
        
        # Summary
        print(f"\n📊 Test Summary:")
        print(f"  POI gap filling: {poi_result.get('status')} ({poi_result.get('filled_items', 0)} items)")
        print(f"  Restaurant gap filling: {restaurant_result.get('status')} ({restaurant_result.get('filled_items', 0)} items)")
        
        if poi_result.get('status') == 'success' and restaurant_result.get('status') == 'success':
            print(f"\n✅ All tests PASSED - Gap agent successfully filled missing data!")
        else:
            print(f"\n❌ Some tests FAILED")
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
